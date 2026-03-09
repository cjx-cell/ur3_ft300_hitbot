cmake_minimum_required(VERSION 3.22)
project(z_efg_f_gripper_config)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 查找依赖（补充必要依赖，和package.xml对应）
find_package(ament_cmake REQUIRED)
find_package(xacro REQUIRED)
find_package(z_efg_f_gripper REQUIRED)

# 安装launch目录（保留所有.launch.py文件，移除无效的EXCLUDE）
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/launch")
  install(
    DIRECTORY launch
    DESTINATION share/${PROJECT_NAME}
    # 仅安装launch.py文件，避免无关文件
    FILES_MATCHING PATTERN "*.launch.py"
  )
endif()

# 安装config目录（包含yaml/xacro/srdf等配置文件）
install(
  DIRECTORY config
  DESTINATION share/${PROJECT_NAME}
  # 仅安装配置相关文件，过滤临时文件
  FILES_MATCHING 
  PATTERN "*.yaml" 
  PATTERN "*.xacro" 
  PATTERN "*.srdf" 
  PATTERN "*.urdf"
)

# 安装MoveIt Setup Assistant生成的隐藏文件（可选，保留）
install(FILES .setup_assistant DESTINATION share/${PROJECT_NAME})

# 安装集成后的URDF文件（如果有ur3_with_gripper_valid.urdf，补充此指令）
# 若文件存在，取消注释：
# install(FILES ur3_with_gripper_valid.urdf DESTINATION share/${PROJECT_NAME})

# ROS2核心规则：ament_package()必须放在所有install指令之后
ament_package()
