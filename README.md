<div align="center">

# zed_slam_bringup

**Real-time visual-inertial SLAM with the Stereolabs ZED 2i on the NVIDIA Jetson Orin Nano.**
Powered by [`zed-ros2-wrapper`](https://github.com/stereolabs/zed-ros2-wrapper) and [`rtabmap_ros`](https://github.com/introlab/rtabmap_ros), tuned for tight thermal and compute budgets.

[![ROS 2 Humble](https://img.shields.io/badge/ROS_2-Humble-blue?logo=ros)](https://docs.ros.org/en/humble/)
[![Platform](https://img.shields.io/badge/platform-Jetson_Orin_Nano-76b900?logo=nvidia&logoColor=white)](https://developer.nvidia.com/embedded/jetson-orin-nano-devkit)
[![Camera](https://img.shields.io/badge/camera-ZED_2i-0b5fff)](https://www.stereolabs.com/products/zed-2)
[![ZED SDK](https://img.shields.io/badge/ZED_SDK-5.2.x-0b5fff)](https://www.stereolabs.com/developers/release/)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-A42E2B.svg)](./LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/soham-verma/Zed2i-Rtabmap-SLAM)](https://github.com/soham-verma/Zed2i-Rtabmap-SLAM/commits/main)

</div>

---

## Overview

`zed_slam_bringup` is a drop-in ROS 2 bringup package that wires three battle-tested components into a single `ros2 launch` command:

1. **ZED SDK** (via `zed_wrapper`) — GPU-accelerated stereo capture, rectification, neural depth, and visual-inertial odometry.
2. **`rgbd_sync`** — approximate-time synchroniser that packs RGB + depth + camera_info into a single `RGBDImage` topic.
3. **RTAB-Map** — graph-based SLAM with place recognition, loop closure, 3D cloud and 2D occupancy grid publishing.

All three are configured through a pair of YAML files tuned specifically for the thermal envelope and compute budget of a Jetson Orin Nano running JetPack + ROS 2 Humble.

> The goal is a **one-command SLAM stack** that you can launch on a robot and immediately drive to build a map — no code, just config.

## Table of contents

- [Features](#features)
- [System architecture](#system-architecture)
- [Quickstart](#quickstart)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running](#running)
- [Driving the robot & building a map](#driving-the-robot--building-a-map)
- [Saving and exporting maps](#saving-and-exporting-maps)
- [Configuration reference](#configuration-reference)
- [Performance on Jetson Orin Nano](#performance-on-jetson-orin-nano)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Features

- **Single-launch pipeline** — one `ros2 launch` spins up camera, odometry, sync, SLAM, and RViz2.
- **Orin-Nano-tuned** — 720p grab, 360p publish at 15 Hz, `NEURAL_LIGHT` depth, reduced feature counts, pre-voxelized output cloud. Keeps frame drops minimal on a ~7 W budget.
- **Live 2D + 3D maps** — `/rtabmap/map` (2D occupancy grid) for Nav2, `/rtabmap/cloud_map` (coloured 3D cloud) for visualisation and mesh export.
- **Loop closure out of the box** — RTAB-Map runs place recognition against a persistent SQLite database at `~/.ros/rtabmap.db`.
- **Resume mapping** — `delete_db:=false` lets you continue a prior session; relaunch in localization-only mode against a saved DB.
- **IMU-aided tracking** — 200 Hz IMU fused via ZED's VIO for robustness to motion blur and low-texture patches.
- **Proper TF tree** — `map → odom → base_link → zed_camera_link`, with one authority per edge (no dueling publishers).
- **Health-probe script** — `validate.sh` dumps node list, topic rates, TF chain, and DB size in one shot.

## System architecture

### Data flow

```
                                     IMU 200 Hz
                          +----------------------------+
                          |                            v
                  +---------------+          +-------------------+
  ZED 2i (USB-3)  |  zed_wrapper  |          |  zed_wrapper VIO  |
  ------------->  |   (SDK: grab, |          |  (pos_tracking)   |
                  |   rectify,    |          +---------+---------+
                  |   GPU depth)  |                    |
                  +---+-------+---+                    | /zed/.../odom (30 Hz)
                      |       |                        | odom TF
             RGB 15Hz |       | Depth 10Hz             |
                      v       v                        |
                +-------------------+                  |
                |    rgbd_sync      |                  |
                |  (approx time)    |                  |
                +---------+---------+                  |
                          |                            |
                          | /rtabmap/rgbd_image (~14Hz)|
                          v                            |
                +-------------------+                  |
                |      rtabmap      |<-----------------+
                |  graph SLAM +     |
                |  loop closure     |
                +---------+---------+
                          |
         +----------------+----------------+-------------------+
         |                |                |                   |
         v                v                v                   v
   /rtabmap/cloud_map  /rtabmap/map   /rtabmap/info       map -> odom TF
     (3D, 5 cm vox)     (2D grid)     (keyframes, loops)
```

### TF tree

```
map                         owned by: rtabmap
 |
 +-- odom                   owned by: zed_wrapper
      |
      +-- base_link         owned by: zed_wrapper (URDF + robot_state_publisher)
           |
           +-- zed_camera_link
                |
                +-- zed_left_camera_frame
                +-- zed_right_camera_frame
                +-- zed_imu_link
                +-- ...
```

There is exactly **one publisher per edge**. An earlier version accidentally published `base_link -> zed_camera_link` twice; that was removed because ZED's own URDF already supplies it.

### Repository layout

```
zed_slam_bringup/
├── CMakeLists.txt                  ament_cmake, installs launch/config/rviz
├── package.xml                     ROS 2 package manifest
├── LICENSE                         GNU AGPL-3.0
├── README.md                       (this file)
├── CHANGELOG.md                    human-readable changelog
├── CONTRIBUTING.md                 contribution guide
├── validate.sh                     runtime health probe
├── launch/
│   ├── slam.launch.py              full pipeline (default entry-point)
│   └── zed_only.launch.py          camera-only sanity test
├── config/
│   ├── zed2i_orinnano.yaml         ZED wrapper overrides for Orin Nano
│   └── rtabmap_orinnano.yaml       RTAB-Map parameters for Orin Nano
├── rviz/
│   └── slam.rviz                   RViz2 display config
├── docs/
│   ├── architecture.md             deeper design notes
│   └── tuning.md                   parameter tuning guide
└── .github/                        issue & PR templates
```

## Quickstart

Assuming the ZED SDK and ROS 2 Humble are already installed on the Jetson:

```bash
# 1. Clone this and the ZED wrapper into a ROS 2 workspace
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone https://github.com/soham-verma/Zed2i-Rtabmap-SLAM.git zed_slam_bringup
git clone -b humble-v5.2.x --recurse-submodules https://github.com/stereolabs/zed-ros2-wrapper.git

# 2. Install dependencies
sudo apt update && sudo apt install -y \
  ros-humble-rtabmap-ros \
  ros-humble-rtabmap-slam \
  ros-humble-rtabmap-sync \
  ros-humble-rtabmap-viz \
  ros-humble-rviz2 \
  ros-humble-nav2-map-server
cd ~/ros2_ws && rosdep install --from-paths src --ignore-src -r -y

# 3. Build
colcon build --symlink-install
source install/setup.bash

# 4. Launch
ros2 launch zed_slam_bringup slam.launch.py
```

RViz2 opens with live camera feed, `/rtabmap/cloud_map`, and the 2D grid. Walk the camera around slowly — every ~5 cm or ~3° of motion adds a keyframe.

## Prerequisites

### Hardware

| Component | Tested with |
|---|---|
| SBC | NVIDIA Jetson Orin Nano 8 GB (dev kit), JetPack 6.x |
| Camera | Stereolabs ZED 2i over USB-3 |
| Storage | NVMe SSD (the RTAB-Map DB can reach several hundred MB per session) |

The same stack runs unmodified on Jetson Xavier NX, Orin NX, Orin AGX, and x86 + dGPU — you'll just have headroom to raise resolution and feature counts.

### Software

| Component | Version |
|---|---|
| Ubuntu | 22.04 (Jammy) |
| ROS 2 | Humble Hawksbill |
| ZED SDK | 5.2.x (must match `zed-ros2-wrapper` branch) |
| CUDA | bundled with JetPack |

### ROS 2 packages

System apt:

```bash
sudo apt install -y \
  ros-humble-rtabmap-ros \
  ros-humble-rtabmap-slam \
  ros-humble-rtabmap-sync \
  ros-humble-rtabmap-viz \
  ros-humble-nav2-map-server \
  ros-humble-rviz2 \
  ros-humble-robot-state-publisher \
  ros-humble-tf2-ros
```

Source (checkout next to this package in `~/ros2_ws/src`):

```bash
git clone -b humble-v5.2.x --recurse-submodules \
  https://github.com/stereolabs/zed-ros2-wrapper.git
```

The branch MUST match your installed ZED SDK — mismatched versions manifest as cryptic topic-path or TF-frame errors.

## Installation

```bash
mkdir -p ~/ros2_ws/src && cd ~/ros2_ws/src
git clone https://github.com/soham-verma/Zed2i-Rtabmap-SLAM.git zed_slam_bringup
git clone -b humble-v5.2.x --recurse-submodules \
  https://github.com/stereolabs/zed-ros2-wrapper.git

cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
echo "source ~/ros2_ws/install/setup.bash" >> ~/.bashrc
source ~/ros2_ws/install/setup.bash
```

Rebuild only this package after tweaking config:

```bash
colcon build --symlink-install --packages-select zed_slam_bringup
```

Because install is `--symlink-install`, editing YAML/launch files in `src/` takes effect on the next launch with no rebuild.

## Running

### Full SLAM + RViz2

```bash
ros2 launch zed_slam_bringup slam.launch.py
```

### Launch arguments

| Argument | Default | Description |
|---|---|---|
| `rviz` | `true` | Start RViz2 with the bundled display config. |
| `delete_db` | `true` | Pass `-d` to RTAB-Map so it wipes `~/.ros/rtabmap.db`. Set to `false` to resume a previous session. |

### Common invocations

```bash
# Headless (e.g. on a robot)
ros2 launch zed_slam_bringup slam.launch.py rviz:=false

# Resume mapping from a previous run
ros2 launch zed_slam_bringup slam.launch.py delete_db:=false

# Camera only - useful for verifying the ZED before adding SLAM
ros2 launch zed_slam_bringup zed_only.launch.py
```

### Startup timing

`slam.launch.py` intentionally staggers startup so the ZED has time to finish IMU warmup and publish its first TF frames before downstream subscribers come online:

| t (s) | Action |
|---|---|
| 0 | `zed_wrapper` starts |
| 6 | `rgbd_sync` + `rtabmap` start |
| 9 | RViz2 starts |

### Runtime health check

```bash
./src/zed_slam_bringup/validate.sh
```

Expected output includes node list, topic rates, a nonzero `ref_id` in `/rtabmap/info`, and three resolved TF chains.

## Driving the robot & building a map

1. Start the launch file and wait ~10 s for RViz2.
2. In RViz2, confirm **Fixed Frame** is `map` and these displays are active:
   - `RTAB Map Cloud` on `/rtabmap/cloud_map` (accumulated, in `map`).
   - `RTAB 2D Grid` on `/rtabmap/map` (occupancy grid).
   - `ZED Cloud` on `/zed/zed_node/point_cloud/cloud_registered` (live current frame).
3. Move the camera slowly. New keyframes fire every **5 cm of translation** or **3° of rotation** (`RGBD/LinearUpdate` / `RGBD/AngularUpdate`).
4. Revisit a previously-observed area to trigger loop closure — the graph is re-optimised and the map "snaps" into alignment.
5. Monitor progress:

   ```bash
   watch -n 1 'ros2 topic echo /rtabmap/info --once | grep -E "ref_id|loop_closure"'
   ```

### Motion best practices

- **Slow, continuous motion.** Fast rotation or jerky motion causes blur and feature-tracking loss.
- **Keep texture in view.** RTAB-Map uses visual features; blank walls or glare will make tracking drop.
- **Light matters.** `NEURAL_LIGHT` depth handles dim scenes better than classic stereo, but very low light still hurts RGB-based matching.
- **Return through known space.** Loop closures improve global consistency far more than adding new territory.

## Saving and exporting maps

The canonical artefact is the RTAB-Map database at `~/.ros/rtabmap.db` — everything else (grids, clouds, meshes) is derived from it.

### 2D occupancy grid (for Nav2)

```bash
mkdir -p ~/maps && cd ~/maps
ros2 run nav2_map_server map_saver_cli -t /rtabmap/map -f my_map
# produces my_map.pgm + my_map.yaml
```

### 3D point cloud (PLY)

Stop the launch first so the DB is flushed:

```bash
rtabmap-export --cloud --voxel 0.02 \
  --output_dir ~/maps --output zed_map \
  ~/.ros/rtabmap.db
```

Produces `~/maps/zed_map_cloud.ply` (RGB coloured, 2 cm voxel).

### Textured mesh (OBJ + texture)

```bash
rtabmap-export --mesh --texture \
  --output_dir ~/maps --output zed_mesh \
  ~/.ros/rtabmap.db
```

Best viewed in CloudCompare or Blender — MeshLab's OBJ parser is known to crash on this file.

### Vertex-coloured mesh (PLY)

Opens reliably in MeshLab, at slightly lower visual fidelity than the textured OBJ:

```bash
rtabmap-export --mesh \
  --output_dir ~/maps --output zed_mesh_vc \
  ~/.ros/rtabmap.db
```

### Snapshot the session

```bash
cp ~/.ros/rtabmap.db ~/maps/session_$(date +%Y%m%d_%H%M).db
```

### Reload a saved DB in localization-only mode

```bash
ros2 launch rtabmap_launch rtabmap.launch.py \
  database_path:=$HOME/maps/session_YYYYMMDD_HHMM.db \
  localization:=true \
  rviz:=true
```

### Choosing a viewer

| Artefact | Recommended viewer |
|---|---|
| RTAB-Map DB | `rtabmap-databaseViewer <file.db>` (graph + cloud + keyframes) |
| PLY (cloud or mesh) | MeshLab, CloudCompare, `pcl_viewer` (after `pcl_ply2pcd`) |
| OBJ (textured) | CloudCompare, Blender |
| PGM + YAML | RViz2 `Map` display, any image viewer |

## Configuration reference

### `config/zed2i_orinnano.yaml`

Full file commented inline; the important knobs:

| Parameter | Value | Why |
|---|---|---|
| `general.grab_resolution` | `HD720` | 720p stereo at 30 fps fits the Orin Nano thermal budget. |
| `general.pub_downscale_factor` | `2.0` | Publishes 360p images — plenty for SLAM features. |
| `general.pub_frame_rate` | `15.0` | Caps published rate regardless of grab. |
| `depth.depth_mode` | `NEURAL_LIGHT` | Best quality/cost tradeoff on this class of Jetson. |
| `depth.min_depth` / `max_depth` | `0.3` / `10.0` m | Reasonable indoor range; raise for outdoor use. |
| `pos_tracking.pos_tracking_mode` | `GEN_1` | Stable VIO with lower compute cost than `GEN_3`. |
| `pos_tracking.publish_map_tf` | `false` | RTAB-Map owns `map → odom`. |
| `pos_tracking.area_memory` | `false` | Disables ZED's own loop closure so RTAB-Map alone is authoritative. |
| `mapping.mapping_enabled` | `false` | ZED spatial mapping off; RTAB-Map handles mapping. |

### `config/rtabmap_orinnano.yaml`

| Parameter | Value | Why |
|---|---|---|
| `subscribe_rgbd` | `true` | One packed topic from `rgbd_sync` — one callback instead of three. |
| `approx_sync` | `true` | ZED's RGB/depth rates vary; exact sync would drop frames. |
| `wait_for_transform` | `1.0` | Tolerates brief odom-TF latency during ZED init. |
| `Kp/MaxFeatures` | `400` | Features for place recognition; trimmed for Orin Nano. |
| `Vis/MaxFeatures` | `600` | Features for motion estimation. |
| `RGBD/LinearUpdate` | `0.05` m | Keyframe every 5 cm of translation. |
| `RGBD/AngularUpdate` | `0.05` rad | Keyframe every ~3° of rotation. |
| `Grid/CellSize` | `0.05` m | 5 cm occupancy cells. |
| `Grid/RangeMax` | `6.0` m | Cap grid build range. |
| `cloud_voxel_size` | `0.05` m | Pre-voxelize `/rtabmap/cloud_map` so RViz stays smooth. |

See [`docs/tuning.md`](docs/tuning.md) for a deeper tuning guide (raising accuracy at the cost of Hz, outdoor ranges, loop closure aggressiveness, etc.).

## Performance on Jetson Orin Nano

Measured on an 8 GB Orin Nano dev kit, JetPack 6.x, 15 W power mode, indoor office:

| Topic | Rate | Notes |
|---|---|---|
| `/zed/zed_node/rgb/color/rect/image` | 5.8 – 10 Hz | Varies with scene complexity; NEURAL_LIGHT depth is the bottleneck. |
| `/zed/zed_node/depth/depth_registered` | 6.4 – 10 Hz | |
| `/zed/zed_node/point_cloud/cloud_registered` | 4 – 6 Hz | |
| `/zed/zed_node/odom` | ~29 Hz | VIO output. |
| `/zed/zed_node/imu/data` | ~198 Hz | |
| `/rtabmap/rgbd_image` | ~14 Hz | Sync multiplies effective rate. |
| `/rtabmap/map` & `cloud_map` | On keyframe | Published per new keyframe. |

On a hotter day or fanless enclosure, expect the depth pipeline to throttle to ~5 Hz. Drop `depth_mode` to `PERFORMANCE` if that becomes a problem — you lose ~15 % depth completeness but gain ~2 Hz.

## Troubleshooting

<details>
<summary><b>Nothing appears in RViz2 / <code>cloud_map</code> is empty</b></summary>

- Confirm Fixed Frame is `map`. If `map → odom` isn't in the TF tree, RTAB-Map hasn't initialised yet — check `/rtabmap/info` is publishing.
- `/rtabmap/cloud_map` only publishes on new keyframes. Move the camera ~10 cm.
- Check `/rtabmap/rgbd_image` is flowing:
  ```bash
  ros2 topic hz /rtabmap/rgbd_image
  ```
  If zero: `rgbd_sync` has a topic remap or QoS mismatch.

</details>

<details>
<summary><b><code>Failed init_port fastrtps_port...</code> on every run</b></summary>

Stale shared-memory segments from a prior ROS 2 process. Harmless but noisy:

```bash
rm -f /dev/shm/fastrtps_*
```

</details>

<details>
<summary><b>ZED RGB rate far below 15 Hz</b></summary>

- Check `tegrastats` for thermal throttling.
- Competing GPU workloads (e.g. another CUDA process) will starve the SDK.
- Drop `depth.depth_mode` to `PERFORMANCE` in `zed2i_orinnano.yaml`.
- Lower `general.pub_frame_rate`.

</details>

<details>
<summary><b>Tracking gets lost during fast motion</b></summary>

- Move slower. SLAM tracks features frame-to-frame; motion blur kills that.
- Ensure at least one textured region is in view at all times.
- RTAB-Map will usually recover when you re-observe a known area via loop closure.

</details>

<details>
<summary><b><code>rtabmap-databaseViewer</code> exits immediately</b></summary>

No `DISPLAY` (SSH without X forwarding). Either run it on the Orin's attached screen, reconnect with `ssh -X`, or try:

```bash
QT_QPA_PLATFORM=xcb rtabmap-databaseViewer ~/.ros/rtabmap.db
```

</details>

<details>
<summary><b>MeshLab crashes opening a <code>rtabmap-export --texture</code> OBJ</b></summary>

Known parser bug in MeshLab's OBJ loader. Open the textured OBJ in CloudCompare or Blender, or re-export as vertex-coloured PLY:

```bash
rtabmap-export --mesh --output_dir ~/maps --output zed_mesh_vc ~/.ros/rtabmap.db
meshlab ~/maps/zed_mesh_vc_mesh.ply
```

</details>

<details>
<summary><b>TF tree is disconnected</b></summary>

```bash
ros2 run tf2_tools view_frames
```

- `base_link` missing: ensure ZED's own URDF is running (`publish_tf: true`).
- Two publishers on one edge: don't add a manual `base_link → zed_camera_link` static TF; ZED already publishes it.

</details>

## Roadmap

- [ ] Nav2 integration example — planner + controller using the saved 2D grid
- [ ] Outdoor preset YAML — wider depth range, GNSS fusion
- [ ] Docker image for reproducible builds on Jetson
- [ ] ROS 2 Jazzy / Iron parameter files
- [ ] GitHub Actions CI: `colcon build` + `ament_lint`
- [ ] Multi-camera bringup (front + rear ZED)
- [ ] Exported mesh → glTF pipeline for web visualisation

Suggestions and PRs welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Contributing

Pull requests are very welcome. Before opening one, please read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the commit-message conventions, testing expectations, and the AGPL licensing implications for contributors.

Bug reports and feature requests via [Issues](https://github.com/soham-verma/Zed2i-Rtabmap-SLAM/issues) — the templates will prompt you for the diagnostics that make triage fast.

## Acknowledgments

This package is a thin wrapper around world-class open-source work. Please support the upstream projects:

- [**Stereolabs** `zed-ros2-wrapper`](https://github.com/stereolabs/zed-ros2-wrapper) — the ZED SDK and its ROS 2 bindings.
- [**IntRoLab** `rtabmap_ros`](https://github.com/introlab/rtabmap_ros) — Mathieu Labbé's remarkable graph SLAM engine.
- [**Open Robotics** ROS 2](https://docs.ros.org/en/humble/) and [**Nav2**](https://docs.nav2.org/).

## License

**GNU Affero General Public License v3.0 only (AGPL-3.0-only).** See [`LICENSE`](LICENSE).

Copyright (C) 2026 Soham Verma.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

> **Why AGPL?** The AGPL is a strong copyleft: any fork, derivative, or network-deployed service using this code must release its full modified source under the same licence to its users. If that's incompatible with your use case, do not use this code — or reach out to discuss alternative licensing.
