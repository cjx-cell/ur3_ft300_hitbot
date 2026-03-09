#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
from ur_msgs.srv import SetIO
from sensor_msgs.msg import JointState

class GripperTestService(Node):
    def __init__(self):
        super().__init__('gripper_test_service')

        # 配置和桥接节点保持一致
        self.GRIPPER_PIN = 16
        self.GRIPPER_FUN = 1
        self.OPEN_IO_STATE = 1.0
        self.CLOSE_IO_STATE = 0.0
        self.OPEN_JOINT_VAL = 0.00
        self.CLOSED_JOINT_VAL = -0.04
        self.JOINT_NAMES = ["z_efg_f_finger_left_joint", "z_efg_f_finger_right_joint"]

        # 连接IO服务
        self.io_client = self.create_client(SetIO, '/io_and_status_controller/set_io')
        while not self.io_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().info('等待IO服务...')

        # 发布关节状态
        self.joint_pub = self.create_publisher(JointState, '/joint_states', 10)

        # 创建测试服务
        self.open_srv = self.create_service(Trigger, '/gripper/test_open', self.open_gripper)
        self.close_srv = self.create_service(Trigger, '/gripper/test_close', self.close_gripper)
        self.get_logger().info('✅ 夹爪测试服务已启动：/gripper/test_open /gripper/test_close')

    def open_gripper(self, req, res):
        return self.control_gripper(True, res)

    def close_gripper(self, req, res):
        return self.control_gripper(False, res)

    def control_gripper(self, open_flag, res):
        try:
            # 调用IO服务
            io_req = SetIO.Request()
            io_req.fun = self.GRIPPER_FUN
            io_req.pin = self.GRIPPER_PIN
            io_req.state = self.OPEN_IO_STATE if open_flag else self.CLOSE_IO_STATE
            future = self.io_client.call_async(io_req)
            rclpy.spin_until_future_complete(self, future)

            if future.result().success:
                # 发布关节状态
                joint_state = JointState()
                joint_state.name = self.JOINT_NAMES
                joint_state.position = [self.OPEN_JOINT_VAL if open_flag else self.CLOSED_JOINT_VAL] * 2
                joint_state.header.stamp = self.get_clock().now().to_msg()
                self.joint_pub.publish(joint_state)

                res.success = True
                res.message = f"夹爪{'打开' if open_flag else '闭合'}成功（IO+关节状态同步）"
            else:
                res.success = False
                res.message = "IO调用失败"
        except Exception as e:
            res.success = False
            res.message = f"失败：{str(e)}"
        return res

def main(args=None):
    rclpy.init(args=args)
    node = GripperTestService()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
