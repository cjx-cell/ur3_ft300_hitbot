#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from action_msgs.msg import GoalStatus
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, JointConstraint
from ur_msgs.srv import SetIO
from sensor_msgs.msg import JointState
from ur_msgs.msg import IOStates

class GripperMoveItIOBridge(Node):
    def __init__(self):
        super().__init__('gripper_moveit_io_bridge')
        self.cb_group = ReentrantCallbackGroup()

        # ====================== 核心配置 ======================
        self.GRIPPER_PIN = 16                  
        self.GRIPPER_FUN = 1                   
        self.OPEN_IO_FLOAT = 1.0               
        self.CLOSE_IO_FLOAT = 0.0              
        self.OPEN_IO_BOOL = True               
        self.CLOSE_IO_BOOL = False             
        
        # 替换为你的实际规划组名（如ur5_gripper/ur10_gripper）
        self.GRIPPER_GROUP_NAME = "gripper"    
        
        self.GRIPPER_JOINTS = [
            "z_efg_f_finger_left_joint",       
            "z_efg_f_finger_right_joint"       
        ]
        
        self.OPEN_THRESH = -0.002               
        self.CLOSE_THRESH = -0.0035             
        # ==================================================================

        # 连接IO服务
        self.io_client = self.create_client(
            SetIO, 
            '/io_and_status_controller/set_io',
            callback_group=self.cb_group
        )
        while not self.io_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('等待IO服务可用...')
        self.get_logger().info('✅ IO服务已连接')

        # 监听MoveGroup的goal指令
        self.move_group_goal_sub = self.create_subscription(
            MoveGroup.Goal,
            '/move_group/goal',
            self.move_group_goal_callback,
            10,
            callback_group=self.cb_group
        )
        self.get_logger().info('✅ 已监听MoveGroup Action请求')

        # 订阅IO状态
        self.io_state_sub = self.create_subscription(
            IOStates,
            '/io_and_status_controller/io_states',
            self.io_state_callback,
            10,
            callback_group=self.cb_group
        )
        self.get_logger().info('✅ 已订阅IO状态（读取夹爪实际电平）')

        # 发布夹爪关节状态（★完全重构：避免字段扩展错误★）
        self.joint_state_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.robot_joint_state_callback,
            10,
            callback_group=self.cb_group
        )
        self.joint_pub = self.create_publisher(JointState, '/joint_states', 10, callback_group=self.cb_group)
        # 初始化完整关节状态为空list，避免tuple干扰
        self.robot_joint_names = []
        self.robot_joint_positions = []
        self.robot_joint_velocities = []
        self.robot_joint_efforts = []
        self.gripper_joint_vals = [-0.004, -0.004]  # 夹爪默认状态

        # 降低发布频率
        self.joint_timer = self.create_timer(
            0.2,
            self.pub_full_joint_state,
            callback_group=self.cb_group
        )

        # 状态标记
        self.last_io_state = None
        self.current_io_bool = False  

    def io_state_callback(self, msg):
        """解析IO状态"""
        try:
            for digital_out in msg.digital_out_states:
                if digital_out.pin == self.GRIPPER_PIN:
                    self.current_io_bool = digital_out.state
                    self.get_logger().info(
                        f'🔍 当前IO{self.GRIPPER_PIN}状态：{self.current_io_bool} | '
                        f'{"夹爪打开（高电平）" if self.current_io_bool else "夹爪闭合（低电平）"}'
                    )
                    # 更新夹爪关节值
                    if self.current_io_bool == self.OPEN_IO_BOOL:
                        self.gripper_joint_vals = [0.00, 0.00]
                    else:
                        self.gripper_joint_vals = [-0.004, -0.004]
                    break
        except Exception as e:
            self.get_logger().warn(f'解析IO状态异常：{str(e)}')

    def robot_joint_state_callback(self, msg):
        """★终极修正：拆分存储机械臂关节数据，完全避免tuple扩展★"""
        try:
            # 1. 单独存储机械臂关节数据（全部转list，空值则初始化为空list）
            self.robot_joint_names = list(msg.name) if msg.name else []
            self.robot_joint_positions = list(msg.position) if msg.position else []
            self.robot_joint_velocities = list(msg.velocity) if msg.velocity else []
            self.robot_joint_efforts = list(msg.effort) if msg.effort else []
        except Exception as e:
            self.get_logger().warn(f'处理机械臂关节状态异常：{str(e)}')

    def move_group_goal_callback(self, goal_msg):
        """解析MoveGroup的Goal指令"""
        try:
            goal_group = goal_msg.request.group_name
            if goal_group != self.GRIPPER_GROUP_NAME:
                return

            if not goal_msg.request.goal_constraints:
                self.get_logger().warn('❌ Goal无约束条件，跳过')
                return
                
            goal_constraints = goal_msg.request.goal_constraints[0]
            if not goal_constraints.joint_constraints:
                self.get_logger().warn('❌ 无关节约束，跳过')
                return

            gripper_target = None
            for jc in goal_constraints.joint_constraints:
                if jc.joint_name in self.GRIPPER_JOINTS:
                    gripper_target = jc.position
                    break

            if gripper_target is None:
                self.get_logger().warn(f'❌ 未找到{self.GRIPPER_JOINTS}的约束，跳过')
                return

            # 判断开合状态
            if gripper_target > self.OPEN_THRESH:
                self.control_gripper(True, gripper_target)
            elif gripper_target < self.CLOSE_THRESH:
                self.control_gripper(False, gripper_target)

        except Exception as e:
            self.get_logger().error(f'解析MoveGroup指令异常：{str(e)}')

    def control_gripper(self, open_flag, target_val):
        """调用IO服务控制夹爪"""
        target_io_bool = self.OPEN_IO_BOOL if open_flag else self.CLOSE_IO_BOOL
        if self.last_io_state == target_io_bool:
            return
        self.last_io_state = target_io_bool

        req = SetIO.Request()
        req.fun = self.GRIPPER_FUN
        req.pin = self.GRIPPER_PIN
        req.state = self.OPEN_IO_FLOAT if open_flag else self.CLOSE_IO_FLOAT

        try:
            future = self.io_client.call_async(req)
            rclpy.spin_until_future_complete(self, future, timeout_sec=1.0)
            
            if future.result().success:
                self.get_logger().info(
                    f'✅ 夹爪{"打开" if open_flag else "闭合"}成功 | '
                    f'指令值：{req.state} | 目标关节值：{target_val}'
                )
                self.gripper_joint_vals = [target_val, target_val]
            else:
                self.get_logger().error(f'❌ 夹爪{"打开" if open_flag else "闭合"}失败：IO服务返回失败')

        except Exception as e:
            self.get_logger().error(f'IO服务调用异常：{str(e)}')

    def pub_full_joint_state(self):
        """★重构发布逻辑：手动构建完整JointState，无tuple扩展★"""
        try:
            # 1. 新建空的JointState
            full_joint_state = JointState()
            full_joint_state.header.stamp = self.get_clock().now().to_msg()
            
            # 2. 拼接机械臂+夹爪关节数据（全部为list，无类型冲突）
            # 关节名
            full_joint_state.name = self.robot_joint_names + self.GRIPPER_JOINTS
            # 关节位置
            full_joint_state.position = self.robot_joint_positions + self.gripper_joint_vals
            # 关节速度（机械臂速度+夹爪0速度）
            full_joint_state.velocity = self.robot_joint_velocities + [0.0, 0.0]
            # 关节力矩（机械臂力矩+夹爪0力矩）
            full_joint_state.effort = self.robot_joint_efforts + [0.0, 0.0]
            
            # 3. 仅当有机械臂关节数据时发布（避免空数据）
            if len(self.robot_joint_names) > 0:
                self.joint_pub.publish(full_joint_state)
        except Exception as e:
            self.get_logger().warn(f'发布关节状态异常：{str(e)}')

def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = GripperMoveItIOBridge()
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        if node:
            node.get_logger().info('🛑 夹爪桥接节点已停止')
    except Exception as e:
        if node:
            node.get_logger().error(f'节点运行异常：{str(e)}')
    finally:
        if rclpy.ok():
            if node:
                node.destroy_node()
            rclpy.shutdown()

if __name__ == '__main__':
    main()
