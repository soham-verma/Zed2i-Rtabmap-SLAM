# zed_slam_bringup

ZED 2i + RTAB-Map SLAM bringup, tuned for a Jetson Orin Nano running ROS 2 Humble.

This package contains **no custom nodes** — just launch glue, parameter overrides, and an RViz2 config that wire three existing components together:

- [`zed_wrapper`](https://github.com/stereolabs/zed-ros2-wrapper) (SDK 5.2.x): stereo capture, rectification, GPU depth, visual-inertial odometry, TF.
- [`rtabmap_sync/rgbd_sync`](https://github.com/introlab/rtabmap_ros): packs RGB + depth + camera_info into one `RGBDImage` stream.
- [`rtabmap_slam/rtabmap`](https://github.com/introlab/rtabmap_ros): graph SLAM with loop closure, publishes the `map -> odom` TF and the accumulated cloud / 2D grid.

## Pipeline

```
                 (IMU, odom, TFs)
┌──────────────┐────────────────────────────────┐
│  zed_wrapper │  /zed/zed_node/rgb/color/rect  │
│  (SDK: grab, │  /zed/zed_node/depth/…         │
│  depth, VIO) │                                ▼
└──────────────┘                    ┌──────────────────────┐
       │  /zed/zed_node/odom        │  rgbd_sync           │
       │  /zed/zed_node/imu/data    │  (approx sync)       │
       │                            └──────────┬───────────┘
       │                                       │ /rtabmap/rgbd_image
       │                                       ▼
       │                            ┌──────────────────────┐
       └───────────────────────────▶│  rtabmap             │
                                    │  keyframes, loop     │
                                    │  closure, map->odom  │
                                    └──────────┬───────────┘
                                               │  /rtabmap/cloud_map
                                               │  /rtabmap/map (2D grid)
                                               ▼
                                             RViz2
```

**TF tree**: `map` → `odom` → `base_link` → `zed_camera_link` → optical frames.
RTAB-Map owns `map → odom`. The ZED wrapper owns `odom → zed_camera_link` and `base_link → zed_camera_link` (via its URDF + `robot_state_publisher`).

## Layout

```
zed_slam_bringup/
├── CMakeLists.txt
├── package.xml
├── launch/
│   ├── slam.launch.py        # full pipeline (default)
│   └── zed_only.launch.py    # camera sanity test
├── config/
│   ├── zed2i_orinnano.yaml   # ZED wrapper overrides (720p@30 grab, 15 Hz publish, NEURAL_LIGHT depth)
│   └── rtabmap_orinnano.yaml # RTAB-Map params tuned for Orin Nano
├── rviz/slam.rviz
└── validate.sh
```

## Prerequisites

- Jetson Orin Nano with ZED 2i on USB 3.
- NVIDIA JetPack + ZED SDK 5.2.x (matching wrapper branch).
- ROS 2 Humble.
- Workspace packages (cloned / apt-installed alongside this one):
  - `zed_wrapper` + `zed_components` (from [zed-ros2-wrapper](https://github.com/stereolabs/zed-ros2-wrapper), `humble-v5.2.x` branch)
  - `rtabmap_ros`, `rtabmap_slam`, `rtabmap_sync`, `rtabmap_viz`

## Build

```bash
cd ~/ros2_ws
colcon build --symlink-install --packages-select zed_slam_bringup
source install/setup.bash
```

Rebuild the whole workspace on first checkout:

```bash
colcon build --symlink-install
```

## Run

Full SLAM stack + RViz2 (wipes the previous database):

```bash
ros2 launch zed_slam_bringup slam.launch.py
```

Resume mapping from the existing `~/.ros/rtabmap.db`:

```bash
ros2 launch zed_slam_bringup slam.launch.py delete_db:=false
```

Headless:

```bash
ros2 launch zed_slam_bringup slam.launch.py rviz:=false
```

Camera only (no SLAM, for topic/rate debugging):

```bash
ros2 launch zed_slam_bringup zed_only.launch.py
```

### Launch arguments

| Argument     | Default | Meaning                                              |
|--------------|---------|------------------------------------------------------|
| `rviz`       | `true`  | Start RViz2 with the bundled config.                 |
| `delete_db`  | `true`  | Pass `-d` to RTAB-Map so it wipes `rtabmap.db`.      |

### Startup timing

`slam.launch.py` delays `rgbd_sync` + `rtabmap` by 6 s and RViz2 by 9 s so the ZED has time to finish IMU warmup and start publishing odom + TFs before the SLAM graph subscribes.

## Driving it

Move the camera **slowly**. A new keyframe is added every 5 cm of translation or ~3° of rotation (`RGBD/LinearUpdate` / `RGBD/AngularUpdate`). When you return to a previously-seen area, RTAB-Map closes the loop and the map snaps into alignment.

Live sanity checks:

```bash
ros2 topic hz /zed/zed_node/rgb/color/rect/image        # ~5–10 Hz at 720p
ros2 topic hz /zed/zed_node/depth/depth_registered      # ~6–10 Hz
ros2 topic hz /rtabmap/rgbd_image                       # sync output
ros2 topic echo /rtabmap/info --once | grep ref_id      # keyframe counter
```

In RViz2 the accumulated map is `/rtabmap/cloud_map` (fixed in `map`); the live per-frame cloud is `/zed/zed_node/point_cloud/cloud_registered` (in `zed_camera_link`).

## Saving & exporting the map

The database at `~/.ros/rtabmap.db` is the source of truth — it contains poses, keyframes, loop closures, RGB/depth, and occupancy cells.

**2D occupancy grid** (while the stack is running):

```bash
mkdir -p ~/maps && cd ~/maps
ros2 run nav2_map_server map_saver_cli -t /rtabmap/map -f my_map
# -> my_map.pgm + my_map.yaml
```

**3D point cloud (PLY)** — stop the launch first so the DB is flushed:

```bash
rtabmap-export --cloud --voxel 0.02 \
  --output_dir ~/maps --output zed_map \
  ~/.ros/rtabmap.db
# -> ~/maps/zed_map_cloud.ply
```

**Vertex-colored mesh (PLY)** — cleanest for viewing in MeshLab:

```bash
rtabmap-export --mesh \
  --output_dir ~/maps --output zed_mesh_vc \
  ~/.ros/rtabmap.db
```

**Textured mesh (OBJ + texture)** — open in CloudCompare or Blender (MeshLab's OBJ parser chokes on this file):

```bash
rtabmap-export --mesh --texture \
  --output_dir ~/maps --output zed_mesh \
  ~/.ros/rtabmap.db
```

**Snapshot the DB**:

```bash
cp ~/.ros/rtabmap.db ~/maps/session_$(date +%Y%m%d_%H%M).db
```

**Reload a saved DB in RViz2** (localization-only):

```bash
ros2 launch rtabmap_launch rtabmap.launch.py \
  database_path:=$HOME/maps/session_YYYYMMDD_HHMM.db \
  localization:=true rviz:=true
```

## Key configuration notes

### `config/zed2i_orinnano.yaml`

- `grab_resolution: HD720`, `grab_frame_rate: 30`, `pub_downscale_factor: 2.0`, `pub_frame_rate: 15.0` — 720p capture, 360p publish at 15 Hz to stay inside the Orin Nano thermal budget.
- `depth_mode: NEURAL_LIGHT` — best quality/cost depth on this class of Jetson.
- `pos_tracking_mode: GEN_1`, `imu_fusion: true` — stable VIO, IMU-aided.
- `publish_tf: true`, `publish_map_tf: false` — ZED owns `odom → camera`; RTAB-Map owns `map → odom`.
- `mapping_enabled: false` — ZED's own spatial mapping is off; RTAB-Map does mapping.
- `area_memory: false` — ZED's own loop closure is off; RTAB-Map handles it.

### `config/rtabmap_orinnano.yaml`

- `subscribe_rgbd: true` — one packed topic from `rgbd_sync` (lighter than 3 separate subscriptions).
- `approx_sync: true`, `wait_for_transform: 1.0` — tolerates the ZED's variable RGB/depth rate and brief TF lag.
- `Kp/MaxFeatures: 400`, `Vis/MaxFeatures: 600` — trimmed feature counts for Orin Nano.
- `RGBD/LinearUpdate: 0.05`, `RGBD/AngularUpdate: 0.05` — keyframe every 5 cm or ~3°.
- `Grid/FromDepth: true`, `Grid/CellSize: 0.05`, `Grid/RangeMax: 6.0` — 2D occupancy grid from depth, capped at 6 m.
- `cloud_voxel_size: 0.05` — published `/rtabmap/cloud_map` is pre-voxelized to 5 cm so RViz stays smooth.

## Troubleshooting

**Nothing in `/rtabmap/cloud_map`** — move the camera. The topic only publishes on new keyframes.

**RViz fixed frame errors** — set Fixed Frame to `map`. If the TF tree never gets `map → odom`, RTAB-Map isn't initializing; check `/rtabmap/info` and that `/rtabmap/rgbd_image` is flowing.

**`Failed init_port fastrtps_port…`** — stale shared-memory segments from a previous run. Harmless; clear with:

```bash
rm -f /dev/shm/fastrtps_*
```

**RGB Hz much below 15** — thermal throttling or competing GPU load. Check `tegrastats`. Drop `pub_frame_rate` or switch `depth_mode` to `PERFORMANCE`.

**Tracking lost** — move slower, ensure adequate lighting and texture. RTAB-Map will recover on loop closure once you re-observe a known area.

**`rtabmap-databaseViewer` exits immediately** — no `DISPLAY` (SSH without X forwarding). Run on the Orin's physical session or `ssh -X`. Try `QT_QPA_PLATFORM=xcb rtabmap-databaseViewer …`.

**MeshLab crashes on the textured OBJ** — known parser bug. Use CloudCompare or Blender for the OBJ, or re-export as vertex-colored PLY (`rtabmap-export --mesh` without `--texture`).

## License

BSD-2-Clause. See [`LICENSE`](LICENSE). Copyright (c) 2026, Soham Verma.
