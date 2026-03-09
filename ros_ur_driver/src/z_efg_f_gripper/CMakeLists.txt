cmake_minimum_required(VERSION 3.8)
project(z_efg_f_gripper)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 查找依赖（保留原有）
find_package(ament_cmake REQUIRED)
find_package(urdf REQUIRED)
find_package(xacro REQUIRED)

# 安装核心文件：urdf/dae/srdf（补充srdf，优化文件匹配）
install(DIRECTORY urdf dae srdf
  DESTINATION share/${PROJECT_NAME}
  # 仅安装指定类型文件，避免安装临时/无关文件（可选但推荐）
  FILES_MATCHING 
  PATTERN "*.xacro" 
  PATTERN "*.urdf" 
  PATTERN "*.dae" 
  PATTERN "*.srdf"
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()  # 保留在最后
