#!/usr/bin/env bash
# Quick health probe for the ZED + RTAB-Map bringup.
# Run after `ros2 launch zed_slam_bringup slam.launch.py` is up.
set -u
source /opt/ros/humble/setup.bash
[ -f "$HOME/ros2_ws/install/setup.bash" ] && source "$HOME/ros2_ws/install/setup.bash"

divider() { echo; echo "====================================================="; echo "$1"; echo "====================================================="; }

divider "node list"
ros2 node list

divider "critical topics - 3s hz probe each"
for t in \
  /zed/zed_node/rgb/image_rect_color \
  /zed/zed_node/depth/depth_registered \
  /zed/zed_node/point_cloud/cloud_registered \
  /zed/zed_node/odom \
  /zed/zed_node/imu/data \
  /rtabmap/odom \
  /rtabmap/cloud_map \
  /rtabmap/map
do
  echo "--- $t ---"
  timeout 3 ros2 topic hz "$t" 2>&1 | tail -2
done

divider "TF: map -> odom"
timeout 2 ros2 run tf2_ros tf2_echo map odom 2>&1 | head -12

divider "TF: odom -> zed_camera_link"
timeout 2 ros2 run tf2_ros tf2_echo odom zed_camera_link 2>&1 | head -12

divider "TF: base_link -> zed_camera_link"
timeout 2 ros2 run tf2_ros tf2_echo base_link zed_camera_link 2>&1 | head -12
