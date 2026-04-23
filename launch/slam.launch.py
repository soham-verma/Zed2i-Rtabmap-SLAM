"""
Full SLAM bringup: ZED 2i + static base_link->zed TF + rgbd_sync + RTAB-Map + RViz2.

ZED SDK performs stereo capture, depth, and VIO on the GPU.
rgbd_sync packs RGB + depth + camera_info into a single RGBDImage message.
RTAB-Map consumes the packed stream + ZED odom, builds map, publishes map->odom TF.

Usage:
    ros2 launch zed_slam_bringup slam.launch.py
    ros2 launch zed_slam_bringup slam.launch.py rviz:=false
    ros2 launch zed_slam_bringup slam.launch.py delete_db:=false
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg = get_package_share_directory('zed_slam_bringup')
    zed_yaml = os.path.join(pkg, 'config', 'zed2i_orinnano.yaml')
    rtab_yaml = os.path.join(pkg, 'config', 'rtabmap_orinnano.yaml')
    rviz_cfg = os.path.join(pkg, 'rviz', 'slam.rviz')

    use_rviz = LaunchConfiguration('rviz')
    delete_db = LaunchConfiguration('delete_db')

    # --- ZED wrapper: capture + rectify + depth + VIO ---
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

    # --- RGB-D sync: packs RGB + depth + camera_info -> /rgbd_image ---
    rgbd_sync_node = Node(
        package='rtabmap_sync',
        executable='rgbd_sync',
        name='rgbd_sync',
        namespace='rtabmap',
        output='screen',
        parameters=[{
            'approx_sync': True,
            'queue_size': 10,
            'qos': 1,
        }],
        remappings=[
            ('rgb/image',       '/zed/zed_node/rgb/color/rect/image'),
            ('rgb/camera_info', '/zed/zed_node/rgb/color/rect/camera_info'),
            ('depth/image',     '/zed/zed_node/depth/depth_registered'),
        ],
    )

    # --- RTAB-Map SLAM ---
    rtab_remaps = [
        ('odom', '/zed/zed_node/odom'),
        ('imu',  '/zed/zed_node/imu/data'),
    ]

    rtabmap_fresh = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        namespace='rtabmap',
        output='screen',
        parameters=[rtab_yaml],
        arguments=['-d', '--ros-args', '--log-level', 'warn'],
        condition=IfCondition(delete_db),
        remappings=rtab_remaps,
    )
    rtabmap_keep = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        namespace='rtabmap',
        output='screen',
        parameters=[rtab_yaml],
        arguments=['--ros-args', '--log-level', 'warn'],
        condition=UnlessCondition(delete_db),
        remappings=rtab_remaps,
    )

    rtab_delayed = TimerAction(
        period=6.0,
        actions=[rgbd_sync_node, rtabmap_fresh, rtabmap_keep],
    )

    # --- RViz2 ---
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_cfg],
        output='log',
        condition=IfCondition(use_rviz),
    )
    rviz_delayed = TimerAction(period=9.0, actions=[rviz_node])

    return LaunchDescription([
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('delete_db', default_value='true'),
        zed_launch,
        rtab_delayed,
        rviz_delayed,
    ])
