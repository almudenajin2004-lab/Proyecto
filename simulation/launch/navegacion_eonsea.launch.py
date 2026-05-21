import os
import xacro
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (ExecuteProcess, TimerAction, DeclareLaunchArgument, 
                            LogInfo, AppendEnvironmentVariable)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
# from launch.actions import IncludeLaunchDescription
# from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():

    # 1. Configuración de rutas
    pkg_description = get_package_share_directory('barco_EONSEA_description')
    xacro_file = os.path.join(pkg_description, 'urdf', 'barco_EONSEA.xacro')
    rviz_config_file = os.path.join(pkg_description, 'rviz', 'barco_config.rviz')
    # Procesamos el Xacro
    robot_description_raw = xacro.process_file(xacro_file).toxml()
    WORLD_PATH = os.path.join(pkg_description, 'worlds', 'sydney_regatta.sdf')
    #WORLD_PATH = 'empty.sdf'
    # 2. Argumentos de posición inicial
    x_pose = LaunchConfiguration('x', default='-550.0')
    y_pose = LaunchConfiguration('y', default='175.0')
    z_pose = LaunchConfiguration('z', default='0.5') 
    yaw_pose = LaunchConfiguration('yaw', default='0.0')

    # 3. VARIABLE DE ENTORNO (100% Portátil)
    # Buscamos la ruta de los modelos del barco
    model_path = os.path.join(pkg_description, 'models')

    # Subimos 4 niveles para llegar a /workspace/ y le sumamos 'src'
    workspace_root = os.path.abspath(os.path.join(pkg_description, '../../../../'))
    src_dynamic_path = os.path.join(workspace_root, 'src')

    # Añadimos también la ruta oficial instalada de vrx_gz por si Gazebo la necesita
    pkg_vrx = get_package_share_directory('vrx_gz')

    # Unimos todas las rutas
    gazebo_paths = model_path + ':' + src_dynamic_path + ':' + pkg_vrx
    set_env_gazebo_resource = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        gazebo_paths
    )

    # 4. NODO Robot State Publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description_raw, 'use_sim_time': True}]
    )

    # 5. LANZAR GAZEBO
    gazebo = ExecuteProcess(
        cmd=['gz', 'sim', WORLD_PATH, '-r'],
        output='screen'
    )

    # 6. SPAWN del barco
    spawn_boat = TimerAction(
        period=15.0, 
        actions=[
            Node(
                package='ros_gz_sim',
                executable='create',
                arguments=[
                    '-topic', 'robot_description',
                    '-name', 'barco_EONSEA',
                    '-x', x_pose, '-y', y_pose, '-z', z_pose, '-Y', yaw_pose
                ],
                output='screen'
            )
        ]
    )

    # 7. PUENTE (Bridge) 
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/model/barco_EONSEA/joint/motor_izquierdo_joint/cmd_thrust@std_msgs/msg/Float64@gz.msgs.Double',
            '/model/barco_EONSEA/joint/motor_derecho_joint/cmd_thrust@std_msgs/msg/Float64@gz.msgs.Double',
            
            '/model/barco_EONSEA/odometry@nav_msgs/msg/Odometry@gz.msgs.Odometry',
            '/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model',
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'
        ],
        output='screen'
    )

    # 8. NODO EXCLUSIVO PARA LA CÁMARA
    image_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=['/camara_barco/image_raw', '/camara_barco/camera_info'],
        output='screen'
    )

    # 9. LANZAR RVIZ2 (Con un pequeño retraso para que Gazebo cargue antes)
    pkg_description = get_package_share_directory('barco_EONSEA_description')
    rviz_config_file = os.path.join(pkg_description, 'rviz', 'barco_config.rviz')
    start_rviz = TimerAction(
        period=20.0, # Abre RViz 2 segundos después de que el barco aparezca
        actions=[
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='screen',
                arguments=['-d', rviz_config_file], 
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
     # 10. LANZAR CONTROLADOR (Con un pequeño retraso para que Gazebo cargue antes)
    controlador = TimerAction(
    period=20.0,
    actions=[
    Node(
        package='simulation',
        executable='eonsea_controller',
        name='eonsea_controller',
        output='screen',
        parameters=[{
            'use_sim_time':              True,
            'pid_linear.kp':           1500.0,
            'pid_linear.ki':             50.0,
            'pid_linear.kd':            100.0,
            'pid_linear.integral_max':  800.0,
            'pid_angular.kp':           800.0,
            'pid_angular.ki':            20.0,
            'pid_angular.kd':            60.0,
            'pid_angular.integral_max': 400.0,
            'derivative_filter_coeff':    0.7,
            'thrust_max':              2500.0,
            'thrust_min':             -2500.0,
            'cmd_timeout_s':              0.5,
        }]
    )]
)

    return LaunchDescription([
        set_env_gazebo_resource,
        robot_state_publisher,
        gazebo,
        controlador,
        spawn_boat,
        bridge,
        image_bridge,
        start_rviz  
    ])