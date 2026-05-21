import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    # Ruta a tu nuevo archivo de configuración
    config_file = os.path.join(
        get_package_share_directory('simulation'),
        'config', 'eonsea_joy.yaml'
    )

    return LaunchDescription([
        # Nodo que lee el mando físico y lo traduce a mensajes de ROS (/joy)
        Node(
            package='joy',
            executable='joy_node',
            name='joy_node',
            parameters=[{'deadzone': 0.05}]
        ),
        # Nodo que traduce los mensajes /joy a potencia de motores para el EONSEA
        Node(
            package='joy_teleop',
            executable='joy_teleop',
            name='joy_teleop',
            parameters=[config_file]
        )
    ])