# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-23

### Added

- Initial release of `zed_slam_bringup`.
- `launch/slam.launch.py`: full pipeline — ZED 2i wrapper + `rgbd_sync` + RTAB-Map + RViz2, with staggered startup.
- `launch/zed_only.launch.py`: camera-only sanity-test launch.
- `config/zed2i_orinnano.yaml`: ZED wrapper overrides tuned for Jetson Orin Nano (HD720 grab, 15 Hz publish, `NEURAL_LIGHT` depth, GEN_1 VIO, IMU fusion on).
- `config/rtabmap_orinnano.yaml`: RTAB-Map parameters tuned for Orin Nano (approx-sync RGBD, trimmed feature counts, 5 cm/3° keyframe thresholds, 5 cm pre-voxelized cloud output, 2D occupancy grid from depth).
- `rviz/slam.rviz`: RViz2 config with RTAB-Map cloud, 2D grid, ZED live cloud, TF, image, odometry.
- `validate.sh`: runtime health probe dumping node list, topic rates, TF chains, and DB size.
- README with architecture diagrams, configuration reference, performance notes on Orin Nano, map export walkthrough, and troubleshooting.
- Launch arguments `rviz:=` and `delete_db:=` for headless and resumed-session workflows.
- AGPL-3.0 license.
- Contributor guide, changelog, issue and PR templates.

### Fixed

- RGB topic path updated for ZED wrapper 5.2.x (`rgb/color/rect/image`).
- Removed duplicate `base_link → zed_camera_link` static TF that previously conflicted with the ZED URDF.
- `rtabmap` and `rgbd_sync` moved under the `rtabmap` namespace so output topics land consistently under `/rtabmap/*`.
- Approximate synchronisation enabled with `wait_for_transform: 1.0` to handle the ZED's variable odom-TF rate.
