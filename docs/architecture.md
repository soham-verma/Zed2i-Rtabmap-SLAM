# Architecture

This document expands on the architecture section of the README with the reasoning behind each design choice.

## Design goals

1. **Zero custom code.** Every component is an upstream ROS 2 package (`zed_wrapper`, `rtabmap_sync`, `rtabmap_slam`, `rviz2`). This package contributes only launch glue and YAML. Upstream bug fixes and improvements flow in automatically.
2. **One command to run.** Everything starts from `ros2 launch zed_slam_bringup slam.launch.py`. Staggered startup handles init ordering without user intervention.
3. **Tune for the weakest link.** On Orin Nano the bottleneck is the ZED SDK's GPU depth pipeline at 5–10 Hz. Every other parameter in this stack is chosen to match that rate without starvation or excessive buffering.
4. **Single owner per TF edge.** No duelling publishers. ZED owns `odom → camera` and everything under `base_link`. RTAB-Map owns `map → odom`.

## Component responsibilities

### `zed_wrapper` (from Stereolabs' ROS 2 wrapper)

Drives the ZED SDK on the GPU. Responsibilities:

- **Stereo capture** at `grab_resolution` / `grab_frame_rate` (HD720 @ 30 fps).
- **Rectification** of the stereo pair.
- **Depth estimation** using ZED's neural depth network (`NEURAL_LIGHT` mode).
- **Visual-inertial odometry** fusing stereo + 400 Hz IMU into 30 Hz pose output (`pos_tracking`).
- **TF publication** of `odom → zed_camera_link` and the full `base_link ↔ sensor` chain via the ZED URDF and an embedded `robot_state_publisher` instance.
- **Downscaled publishing** — the camera captures at 720p but publishes at 360p to reduce network/CPU load, since SLAM does not need full resolution.

Published topics we consume:

- `/zed/zed_node/rgb/color/rect/image` — rectified colour.
- `/zed/zed_node/rgb/color/rect/camera_info` — intrinsics.
- `/zed/zed_node/depth/depth_registered` — depth aligned with RGB.
- `/zed/zed_node/odom` — VIO pose at 30 Hz.
- `/zed/zed_node/imu/data` — calibrated IMU at ~200 Hz (feeds RTAB-Map's priors).

Explicitly disabled in `zed2i_orinnano.yaml`:

- `mapping_enabled: false` — ZED's own fused-mapping feature would duplicate RTAB-Map's job.
- `area_memory: false` — ZED's own loop closure would compete with RTAB-Map's and produce a second `map` frame.
- `publish_map_tf: false` — only RTAB-Map should own that edge.

### `rgbd_sync` (from `rtabmap_sync`)

An approximate-time message filter that subscribes to three ZED topics and publishes one `rtabmap_msgs/RGBDImage`:

```
rgb/image, rgb/camera_info, depth/image  --->  rgbd_image
```

Why go through the extra hop?

- RTAB-Map can subscribe to the three topics directly, but that spawns three subscription callbacks per message — on Orin Nano that is measurably more expensive.
- Packing once in `rgbd_sync` and subscribing once in `rtabmap` is about 20 % cheaper CPU.
- The synchroniser is approximate because ZED's RGB and depth publish at slightly different rates and phases — exact sync would drop ~30 % of frames.

Configured parameters:

| Parameter | Value | Rationale |
|---|---|---|
| `approx_sync` | `true` | RGB/depth are not phase-locked. |
| `queue_size` | 10 | Tolerates one or two missed frames without losing sync. |
| `qos` | 1 (BEST_EFFORT) | Matches ZED's image QoS; RELIABLE would cause the subscriber to stall. |

### `rtabmap` (from `rtabmap_slam`)

The SLAM graph itself. Input: one `RGBDImage` topic + one `Odometry` topic (+ optional IMU). Output: updated graph, periodic 2D grid, periodic 3D cloud, and the `map → odom` transform.

Lifecycle per frame:

1. Receive synchronised RGB + depth + odom pose.
2. Extract GFTT features (`Kp/DetectorStrategy: 6`) and compute descriptors.
3. **Short-term memory** check: does this pose clear the linear/angular thresholds? If not, skip.
4. If new keyframe: insert node in the graph, link to the previous node via visual odometry refinement (`RGBD/NeighborLinkRefining`).
5. **Loop-closure check**: compare against working-memory nodes using bag-of-words; if similarity passes `Rtabmap/LoopThr`, run RANSAC PnP to confirm, add loop edge.
6. **Graph optimisation** (g2o by default) when the graph changes.
7. Publish updated cloud/grid if a new keyframe was added.

The SQLite database at `~/.ros/rtabmap.db` persists all keyframes, feature vocabularies, and the graph. Launch argument `delete_db:=true` passes `-d` to wipe it at start; `false` resumes from the existing DB.

### RViz2

A passive visualiser. Its config (`rviz/slam.rviz`) declares displays for:

- **Map grid** (ground plane reference).
- **TF** tree.
- **Image** — live ZED colour.
- **Odometry** — `/rtabmap/odom`.
- **RTAB-Map Cloud** — `/rtabmap/cloud_map` in `map`.
- **RTAB-Map 2D Grid** — `/rtabmap/map`.
- **ZED Cloud** — `/zed/.../cloud_registered` in `zed_camera_link` (live current frame).

Default fixed frame: `map`. Everything renders correctly as long as the TF tree is connected.

## Startup ordering

Three things must happen in order before SLAM can work:

1. ZED node must finish IMU warmup (`wait_imu_to_init: true`).
2. ZED must publish at least one `odom` message and the `odom → camera` TF.
3. RTAB-Map must subscribe.

`slam.launch.py` uses `TimerAction` delays to enforce this without introspection:

- `t=0` — ZED starts.
- `t=6s` — `rgbd_sync` + `rtabmap` start. By this point ZED has always finished init on Orin Nano.
- `t=9s` — RViz2 starts. Delayed so that the first rendered frame already has valid TF.

A more sophisticated launch file would use `event_handlers` watching for the first TF message, but in practice the fixed delays are both simpler and reliable.

## QoS choices

| Topic | QoS | Why |
|---|---|---|
| ZED images | BEST_EFFORT, depth 5 | Match camera drivers' convention. RELIABLE causes stalls on any missed ACK. |
| ZED odom | RELIABLE, depth 10 | Odometry must not drop messages. |
| ZED IMU | BEST_EFFORT, depth 100 | High rate, dropping is fine because RTAB-Map only uses it as a prior. |
| `/rtabmap/rgbd_image` | BEST_EFFORT | Consistent with image QoS. |
| `/rtabmap/cloud_map` | RELIABLE, TRANSIENT_LOCAL | Latched so a late-joining RViz gets the map without waiting for the next keyframe. |
| `/rtabmap/map` | RELIABLE, TRANSIENT_LOCAL | As above. |

## Why not…?

**…use `rtabmap_launch/rtabmap.launch.py` directly?** It exists, it works, but it's a monolith with many knobs. This package gives you a curated subset and hard-codes the good defaults for Orin Nano.

**…use ZED's own spatial mapping?** ZED Spatial Mapping is excellent but fuses depth into a TSDF volume without loop closure or a graph — you cannot correct long-range drift. RTAB-Map can.

**…subscribe to `/zed/zed_node/rgb/image_rect_color`?** That topic name belongs to the ZED wrapper 4.x / earlier 5.x. In SDK 5.2 the wrapper renamed it to `/zed/zed_node/rgb/color/rect/image` and also added `camera_info` under the same prefix. Our YAML and launch file target 5.2.
