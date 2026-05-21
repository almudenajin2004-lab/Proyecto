cmake_minimum_required(VERSION 3.10.2 FATAL_ERROR)

project(simulation)

include(CheckCXXCompilerFlag)
CHECK_CXX_COMPILER_FLAG("-std=c++17" COMPILER_SUPPORTS_CXX17)
if(COMPILER_SUPPORTS_CXX17)
    add_compile_options(-std=c++17)
else()
    message(FATAL_ERROR "The compiler ${CMAKE_CXX_COMPILER} has no C++17 support. Please use a different C++ compiler.")
endif()

find_package(ament_cmake REQUIRED)
find_package(std_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(gz-msgs10 REQUIRED)
find_package(gz-transport13 REQUIRED)
set(GZ_TRANSPORT_VER ${gz-transport13_VERSION_MAJOR})
find_package(rclcpp REQUIRED)
find_package(ros_gz_interfaces REQUIRED)
find_package(rosgraph_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
# Añadir el teleoperador
add_executable(eonsea_teleop src/eonsea_teleop.cpp)
ament_target_dependencies(eonsea_teleop rclcpp std_msgs)
# Añadir el controlador
add_executable(eonsea_controller src/eonsea_controller.cpp)
ament_target_dependencies(eonsea_controller rclcpp geometry_msgs nav_msgs std_msgs)
# Añadir el generador de trayectoria
add_executable(eonsea_trayectoria src/eonsea_trayectoria.cpp)
ament_target_dependencies(eonsea_trayectoria rclcpp geometry_msgs nav_msgs)

# Resources
install(DIRECTORY
  launch
  config
  DESTINATION share/${PROJECT_NAME})
install(TARGETS
  eonsea_teleop
  eonsea_controller
  eonsea_trayectoria
  DESTINATION lib/${PROJECT_NAME}
)  
#install(PROGRAMS
#  launch/eonsea_teleop.py
 # DESTINATION lib/${PROJECT_NAME}
#)
ament_package()
