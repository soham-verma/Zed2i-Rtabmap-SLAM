"""
First-light launch: just the ZED 2i wrapper with Orin-Nano-tuned overrides.
Usage:
    ros2 launch zed_slam_bringup zed_only.launch.py
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg = get_package_share_directory('zed_slam_bringup')
    zed_yaml = os.path.join(pkg, 'config', 'zed2i_orinnano.yaml')

    zed_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('zed_wrapper'),
                'launch',
                'zed_camera.launch.py',
            ])
        ),
        launch_arguments={
            'camera_model': 'zed2i',
            'camera_name': 'zed',
            'ros_params_override_path': zed_yaml,
            'publish_tf': 'true',
            'publish_map_tf': 'false',
        }.items(),
    )

    return LaunchDescription([zed_launch])
