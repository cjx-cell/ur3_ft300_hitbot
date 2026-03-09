ROS 2 Driver Package for UR3 Robotic Arm + Robotiq FT300 Force/Torque Sensor + Hitbot Gripper

rosdep update
rosdep install --ignore-src --from-paths src -y
colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
source install/setup.bash

启动ur3机械臂
ros2 launch ur_robot_driver ur_control.launch.py ur_type:=ur3 robot_ip:=192.168.1.101 launch_rviz:=true

启动规划
ros2 launch ur_moveit_config ur_moveit.launch.py ur_type:=ur3 launch_rviz:=true
ros2 run ur_robot_driver gripper_moveit_io_bridge.py

读取力矩传感器数据
ros2 topic echo /force_torque_sensor_broadcaster/wrench


夹抓开
ros2 service call /io_and_status_controller/set_io ur_msgs/srv/SetIO "{fun: 1, pin: 16, state: 1.0}"

夹抓关
ros2 service call /io_and_status_controller/set_io ur_msgs/srv/SetIO "{fun: 1, pin: 16, state: 0.0}"

io电流状态
ros2 topic echo /io_and_status_controller/io_states
