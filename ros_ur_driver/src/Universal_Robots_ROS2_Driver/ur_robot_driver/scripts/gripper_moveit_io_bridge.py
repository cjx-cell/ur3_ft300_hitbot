#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from ur_msgs.srv import SetIO
from sensor_msgs.msg import JointState
from ur_msgs.msg import IOStates
# 仅使用ROS2原生依赖
from moveit_msgs.msg import PlanningScene, RobotState
from std_msgs.msg import Header

class GripperIOController(Node):
    def __init__(self):
        super().__init__('gripper_io_controller')
        self.cb_group = ReentrantCallbackGroup()

        # ========== 核心配置 ==========
        self.GRIPPER_PIN = 16                  # 夹爪控制IO引脚
        self.GRIPPER_FUN = 1                   # UR数字输出功能码
        self.OPEN_IO_STATE = 1.0               # 打开夹爪IO电平
        self.CLOSE_IO_STATE = 0.0              # 关闭夹爪IO电平
        self.GRIPPER_JOINTS = [                # 夹爪关节名（匹配URDF）
            "z_efg_f_finger_left_joint",       
            "z_efg_f_finger_right_joint"       
        ]
        self.OPEN_JOINT_VAL = [0.0, 0.0]       # 打开关节值
        self.CLOSE_JOINT_VAL = [-0.004, 0.004] # 关闭关节值
        self.last_gripper_vals = None          # 防刷屏

        # ========== 发布Planning Scene（修复版） ==========
        self.planning_scene_pub = self.create_publisher(
            PlanningScene,
            '/planning_scene',
            10,
            callback_group=self.cb_group
        )

        # ========== SetIO服务客户端 ==========
        self.set_io_client = self.create_client(
            SetIO, 
            '/io_and_status_controller/set_io',
            callback_group=self.cb_group
        )
        while not self.set_io_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().info('等待SetIO服务可用...')

        # ========== 订阅/发布器 ==========
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.robot_joint_state_callback,
            10,
            callback_group=self.cb_group
        )
        self.joint_pub = self.create_publisher(JointState, '/joint_states', 10, callback_group=self.cb_group)
        
        self.io_state_sub = self.create_subscription(
            IOStates,
            '/io_and_status_controller/io_states',
            self.io_state_callback,
            10,
            callback_group=self.cb_group
        )

        # ========== ActionServer ==========
        self.action_server = ActionServer(
            self,
            FollowJointTrajectory,
            'gripper_dummy_controller/follow_joint_trajectory',
            execute_callback=self.execute_trajectory_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group
        )

        # ========== 定时任务 ==========
        self.joint_timer = self.create_timer(0.1, self.pub_full_joint_state, callback_group=self.cb_group)

        # ========== 变量初始化 ==========
        self.robot_joint_names = []
        self.robot_joint_positions = []
        self.robot_joint_velocities = []
        self.robot_joint_efforts = []
        self.gripper_joint_vals = self.CLOSE_JOINT_VAL

    # ========== 修复版：更新Planning Scene ==========
    def update_planning_scene(self):
        """兼容所有Humble版本的PlanningScene构造"""
        try:
            planning_scene = PlanningScene()
            planning_scene.is_diff = True  # 先设置is_diff（关键）
            
            # 构造RobotState（带header）
            robot_state = RobotState()
            robot_state.header = Header()
            robot_state.header.stamp = self.get_clock().now().to_msg()
            robot_state.header.frame_id = "base_link"
            # 设置夹爪关节
            robot_state.joint_state.name = self.GRIPPER_JOINTS
            robot_state.joint_state.position = self.gripper_joint_vals
            robot_state.joint_state.header = robot_state.header
            
            # 关联到PlanningScene
            planning_scene.robot_state = robot_state

            self.planning_scene_pub.publish(planning_scene)
            self.get_logger().debug('✅ Planning Scene更新成功')
        except Exception as e:
            self.get_logger().warn(f'更新Planning Scene失败：{str(e)}')

    # ========== ActionServer回调 ==========
    def goal_callback(self, goal_request):
        self.get_logger().info('收到夹爪轨迹执行请求')
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        self.get_logger().info('夹爪执行请求已取消')
        return CancelResponse.ACCEPT

    async def execute_trajectory_callback(self, goal_handle):
        result = FollowJointTrajectory.Result()
        try:
            last_point = goal_handle.request.trajectory.points[-1]
            target_vals = last_point.positions
            old_vals = self.gripper_joint_vals

            # 执行IO控制
            if abs(target_vals[0] - self.OPEN_JOINT_VAL[0]) < 0.001:
                req = SetIO.Request()
                req.fun = self.GRIPPER_FUN
                req.pin = self.GRIPPER_PIN
                req.state = self.OPEN_IO_STATE
                await self.set_io_client.call_async(req)
                self.gripper_joint_vals = self.OPEN_JOINT_VAL
                self.get_logger().info('✅ 执行夹爪打开指令')
            else:
                req = SetIO.Request()
                req.fun = self.GRIPPER_FUN
                req.pin = self.GRIPPER_PIN
                req.state = self.CLOSE_IO_STATE
                await self.set_io_client.call_async(req)
                self.gripper_joint_vals = self.CLOSE_JOINT_VAL
                self.get_logger().info('✅ 执行夹爪关闭指令')
            
            # 更新状态
            if old_vals != self.gripper_joint_vals:
                self.update_planning_scene()

            goal_handle.succeed()
            result.error_code = FollowJointTrajectory.Result.SUCCESSFUL
            return result
        except Exception as e:
            self.get_logger().error(f'执行轨迹失败：{str(e)}')
            result.error_code = FollowJointTrajectory.Result.INVALID_GOAL
            goal_handle.abort()
            return result

    # ========== IO状态回调 ==========
    def io_state_callback(self, msg):
        try:
            old_vals = self.gripper_joint_vals
            for digital_out in msg.digital_out_states:
                if digital_out.pin == self.GRIPPER_PIN:
                    self.gripper_joint_vals = self.OPEN_JOINT_VAL if digital_out.state else self.CLOSE_JOINT_VAL
                    break
            if old_vals != self.gripper_joint_vals:
                self.update_planning_scene()
        except Exception as e:
            self.get_logger().warn(f'解析IO状态异常：{str(e)}')

    # ========== 机械臂关节回调 ==========
    def robot_joint_state_callback(self, msg):
        try:
            self.robot_joint_names = [name for name in msg.name if name not in self.GRIPPER_JOINTS]
            self.robot_joint_positions = [
                pos for i, pos in enumerate(msg.position) if msg.name[i] not in self.GRIPPER_JOINTS
            ]
            self.robot_joint_velocities = [
                vel for i, vel in enumerate(msg.velocity) if msg.name[i] not in self.GRIPPER_JOINTS
            ]
            self.robot_joint_efforts = [
                eff for i, eff in enumerate(msg.effort) if msg.name[i] not in self.GRIPPER_JOINTS
            ]
        except Exception as e:
            self.get_logger().warn(f'处理机械臂关节异常：{str(e)}')

    # ========== 强化版：发布/joint_states ==========
    def pub_full_joint_state(self):
        try:
            full_joint_state = JointState()
            full_joint_state.header.stamp = self.get_clock().now().to_msg()
            full_joint_state.header.frame_id = "base_link"
            full_joint_state.name = self.robot_joint_names + self.GRIPPER_JOINTS
            full_joint_state.position = self.robot_joint_positions + self.gripper_joint_vals
            full_joint_state.velocity = self.robot_joint_velocities + [0.0, 0.0]
            full_joint_state.effort = self.robot_joint_efforts + [0.0, 0.0]

            if len(full_joint_state.name) > 0:
                self.joint_pub.publish(full_joint_state)
                if self.last_gripper_vals != self.gripper_joint_vals:
                    self.last_gripper_vals = self.gripper_joint_vals
                    self.get_logger().info(f'📤 夹爪关节值更新：{self.gripper_joint_vals}')
        except Exception as e:
            self.get_logger().warn(f'发布关节状态异常：{str(e)}')

def main(args=None):
    rclpy.init(args=args)
    node = GripperIOController()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info('🛑 夹爪IO控制器已停止')
    finally:
        node.action_server.destroy()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
