/* Software License Agreement (BSD License)
*
* Copyright (c) 2014, Robotiq, Inc.
* All rights reserved.
*
* Redistribution and use in source and binary forms, with or without
* modification, are permitted provided that the following conditions
* are met:
*
* * Redistributions of source code must retain the above copyright
* notice, this list of conditions and the following disclaimer.
* * Redistributions in binary form must reproduce the above
* copyright notice, this list of conditions and the following
* disclaimer in the documentation and/or other materials provided
* with the distribution.
* * Neither the name of Robotiq, Inc. nor the names of its
* contributors may be used to endorse or promote products derived
* from this software without specific prior written permission.
*
* THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
* "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
* LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
* FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
* COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
* INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
* BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
* CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
* LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
* ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
* POSSIBILITY OF SUCH DAMAGE.
*
* Copyright (c) 2014, Robotiq, Inc
* Adapted for ROS 2 Humble
*/

/**
 * \file rq_test_sensor.cpp
 * \date July 14, 2014
 *  \author Jonathan Savoie <jonathan.savoie@robotiq.com>
 *  \maintainer Jean-Philippe Roberge <ros@robotiq.com>
 *  \adapted for ROS 2 Humble by Your Name
 */

// 1. 替换ROS 1头文件为ROS 2 RCLCPP头文件
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
// ROS 2的msg/srv头文件路径格式（适配首字母大写的文件名）
// 关键修改1：msg头文件从ft_sensor.hpp → FtSensor.hpp
#include "robotiq_ft_sensor/msg/FtSensor.hpp"
// 关键修改2：srv头文件从sensor_accessor.hpp → SensorAccessor.hpp
#include "robotiq_ft_sensor/srv/SensorAccessor.hpp"

#include <sstream>

// 2. 回调函数修改：适配ROS 2的msg类型 + 字段名小写化
void reCallback(const robotiq_ft_sensor::msg::FtSensor::SharedPtr msg)
{
	// 核心修改：Fx→fx、Fy→fy...（匹配修改后的msg文件）
	RCLCPP_INFO(
		rclcpp::get_logger("rq_test_sensor"),
		"I heard: FX[%f] FY[%f] FZ[%f] MX[%f] MY[%f] MZ[%f]",
		msg->fx, msg->fy, msg->fz, msg->mx, msg->my, msg->mz
	);
}

/**
 * This tutorial demonstrates simple sending of messages over the ROS 2 system.
 */
int main(int argc, char **argv)
{
	// 3. ROS 2节点初始化（替换ros::init）
	rclcpp::init(argc, argv);
	// 创建ROS 2节点（替换ros::NodeHandle）
	auto node = rclcpp::Node::make_shared("rq_test_sensor");

	// 4. 创建ROS 2 Service Client（替换ros::ServiceClient，类型已适配SensorAccessor）
	auto client = node->create_client<robotiq_ft_sensor::srv::SensorAccessor>("robotiq_ft_sensor_acc");
	// 5. 创建ROS 2 Subscriber（替换ros::Subscriber，类型已适配FtSensor）
	auto sub1 = node->create_subscription<robotiq_ft_sensor::msg::FtSensor>(
		"robotiq_ft_sensor",  // 话题名和ROS 1保持一致
		100,                  // 队列大小
		&reCallback           // 回调函数
	);

	// 6. 初始化Service请求对象（ROS 2的Service类型路径更长，简化别名）
	using SensorAccessorSrv = robotiq_ft_sensor::srv::SensorAccessor;
	auto srv = std::make_shared<SensorAccessorSrv::Request>();

	int count = 0;
	// 7. 替换ros::ok()为rclcpp::ok()（ROS 2主循环判断）
	while (rclcpp::ok())
	{
		if(count == 10000000)
		{
			/// Deprecated Interface（ROS 1旧接口，ROS 2建议删除）
			// srv->command = "SET ZRO";

			/// New Interface with numerical commands（适配ROS 2）
			srv->command_id = srv->COMMAND_SET_ZERO;

			// 8. ROS 2 Service同步调用（替换client.call(srv)）
			// 先等待Service端上线
			while (!client->wait_for_service(std::chrono::seconds(1))) {
				if (!rclcpp::ok()) {
					RCLCPP_ERROR(node->get_logger(), "Interrupted while waiting for the service. Exiting.");
					return 0;
				}
				RCLCPP_INFO(node->get_logger(), "Service not available, waiting again...");
			}

			// 发送Service请求并获取响应
			auto result = client->async_send_request(srv);
			if (rclcpp::spin_until_future_complete(node, result) == rclcpp::FutureReturnCode::SUCCESS)
			{
				RCLCPP_INFO(node->get_logger(), "ret: %s", result.get()->res.c_str());
			}
			else
			{
				RCLCPP_ERROR(node->get_logger(), "Failed to call service robotiq_ft_sensor_acc");
			}
			count = 0;
		}

		// 9. 替换ros::spinOnce()为rclcpp::spin_some()（处理回调）
		rclcpp::spin_some(node);
		++count;
	}

	// 10. ROS 2节点关闭（可选，rclcpp::shutdown会自动处理）
	rclcpp::shutdown();
	return 0;
}
