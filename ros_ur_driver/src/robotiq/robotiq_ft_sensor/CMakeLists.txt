# 1. 提升CMake版本（Humble要求≥3.8，推荐3.16+）
cmake_minimum_required(VERSION 3.16)
project(robotiq_ft_sensor)

# 2. 强制指定C++17标准（ROS 2 Humble推荐）
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

# 3. 查找ROS 2核心依赖（补充std_srvs，适配零点校准服务）
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)  # WrenchStamped消息依赖
find_package(std_srvs REQUIRED)       # Trigger服务依赖（零点校准）

# 4. 注释自定义msg/srv生成（配合cpp文件修改）
# set(msg_files "msg/FtSensor.msg")
# set(srv_files "srv/SensorAccessor.srv")
# find_package(rosidl_default_generators REQUIRED)
# rosidl_generate_interfaces(${PROJECT_NAME}
#   ${msg_files}
#   ${srv_files}
#   DEPENDENCIES std_msgs
# )

# 5. 包含目录（ROS 2推荐target_include_directories，而非全局）
include_directories(include)

# 6. 编译可执行文件（核心驱动节点）
add_executable(rq_sensor 
  nodes/rq_sensor.cpp 
  src/rq_sensor_com.cpp 
  src/rq_sensor_state.cpp
)

# 7. 绑定依赖（补充std_srvs，解决零点校准服务编译报错）
ament_target_dependencies(rq_sensor
  rclcpp
  std_msgs
  geometry_msgs
  std_srvs  # 新增：对应Trigger服务
)

# 8. 目标级include目录（规范写法）
target_include_directories(rq_sensor
  PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

# 9. 测试节点（可选，如需启用则取消注释）
# add_executable(rq_test_sensor nodes/rq_test_sensor.cpp)
# ament_target_dependencies(rq_test_sensor
#   rclcpp
#   std_msgs
#   geometry_msgs
#   std_srvs
# )

# 10. 安装可执行文件
install(TARGETS
  rq_sensor
  # rq_test_sensor  # 可选：启用测试节点时取消注释
  DESTINATION lib/${PROJECT_NAME}
)

# 11. 安装头文件（便于其他包引用）
install(DIRECTORY include/${PROJECT_NAME}/
  DESTINATION include/${PROJECT_NAME}
)

# 12. 安装静态资源（URDF、meshes）
install(DIRECTORY urdf meshes
  DESTINATION share/${PROJECT_NAME}
)

# 13. ROS 2规范检查（可选，提升包质量）
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

# 14. ament包标记（ROS 2必需）
ament_package()
