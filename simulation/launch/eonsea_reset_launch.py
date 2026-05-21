"""
eonsea_reset_launch.py
====================================================================
Resetea el barco USV EONSEA a su posición inicial SIN reiniciar
el mundo completo de Gazebo. Actualizado para ROS2 Xacro.

USO:
  # Opción A – solo teleportar (más rápido, no reinicia física)
  ros2 launch eonsea_reset_launch.py

  # Opción B – eliminar y volver a crear el modelo desde el tópico de ROS
  ros2 launch eonsea_reset_launch.py mode:=respawn

  # Con posición personalizada
  ros2 launch eonsea_reset_launch.py mode:=teleport x:=-500.0 y:=200.0
====================================================================
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    TimerAction,
    LogInfo,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node

# Constantes Actualizadas
WORLD_NAME = 'sydney_regatta'
ROBOT_NAME = 'barco_EONSEA' # <--- NOMBRE CORRECTO

def generate_launch_description():

    # --- Argumentos (Mismos valores predeterminados que en la navegación) ---
    declare_mode = DeclareLaunchArgument(
        'mode',
        default_value='teleport',
        description='Modo de reset: "teleport" o "respawn"'
    )
    # Valores por defecto idénticos a navegacion_eonsea.launch.py
    declare_x   = DeclareLaunchArgument('x',   default_value='-500.0')
    declare_y   = DeclareLaunchArgument('y',   default_value='175.0')
    declare_z   = DeclareLaunchArgument('z',   default_value='0.5')
    declare_yaw = DeclareLaunchArgument('yaw', default_value='0.0')

    mode = LaunchConfiguration('mode')
    x    = LaunchConfiguration('x')
    y    = LaunchConfiguration('y')
    z    = LaunchConfiguration('z')
    yaw  = LaunchConfiguration('yaw')

    # --- Opción A: TELEPORT via set_pose ---
    teleport = ExecuteProcess(
        cmd=[
            'gz', 'service',
            '-s', f'/world/{WORLD_NAME}/set_pose',
            '--reqtype',  'gz.msgs.Pose',
            '--reptype',  'gz.msgs.Boolean',
            '--timeout',  '5000',
            '--req',
            ['name: "', ROBOT_NAME, '" position: {x: ', x, ', y: ', y, ', z: ', z, '} orientation: {w: 1.0, x: 0.0, y: 0.0, z: 0.0}']
        ],
        output='screen',
        condition=UnlessCondition(PythonExpression(["'", mode, "' == 'respawn'"]))
    )

    # --- Opción B: RESPAWN (borrar + crear de nuevo) ---
    delete_model = ExecuteProcess(
        cmd=[
            'gz', 'service',
            '-s', f'/world/{WORLD_NAME}/remove',
            '--reqtype',  'gz.msgs.Entity',
            '--reptype',  'gz.msgs.Boolean',
            '--timeout',  '5000',
            '--req',      f'name: "{ROBOT_NAME}" type: MODEL'
        ],
        output='screen',
        condition=IfCondition(PythonExpression(["'", mode, "' == 'respawn'"]))
    )

    # Spawn leyendo desde el tópico, ¡NO desde el archivo SDF!
    respawn_boat = TimerAction(
        period=2.0,
        actions=[
            LogInfo(msg='[RESET] Recreando barco desde /robot_description...'),
            Node(
                package='ros_gz_sim',
                executable='create',
                name='respawn_eonsea',
                arguments=[
                    '-topic', 'robot_description', # <--- LEE EL XACRO EN MEMORIA
                    '-name',  ROBOT_NAME,
                    '-x',     x,
                    '-y',     y,
                    '-z',     z,
                    '-Y',     yaw,
                ],
                output='screen',
                condition=IfCondition(PythonExpression(["'", mode, "' == 'respawn'"]))
            )
        ]
    )

    return LaunchDescription([
        declare_mode,
        declare_x,
        declare_y,
        declare_z,
        declare_yaw,
        LogInfo(msg=f'[EONSEA] Ejecutando reset del barco ({ROBOT_NAME})...'),
        teleport,
        delete_model,
        respawn_boat,
    ])