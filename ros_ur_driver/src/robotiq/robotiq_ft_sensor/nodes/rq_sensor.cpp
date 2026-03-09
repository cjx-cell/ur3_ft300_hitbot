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
*/

/**
 * \file rq_sensor.cpp
 * \date July 14, 2014
 *  \author Jonathan Savoie <jonathan.savoie@robotiq.com>
 *  \maintainer Jean-Philippe Roberge <ros@robotiq.com>
 *  \adapted for ROS 2 Humble by Your Name
 */

#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <chrono>
#include <functional>  // 新增：绑定回调函数所需

// ROS 2核心头文件
#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/wrench_stamped.hpp"
#include "std_srvs/srv/trigger.hpp"  // 标准Trigger服务（用于零点校准）
#include "robotiq_ft_sensor/rq_sensor_state.h"
#include "robotiq_ft_sensor/rq_sensor_com.h"  // 新增：直接调用串口函数

// 全局参数
static int max_retries_(100);
std::string ftdi_id;
std::string serial_port_;  // 串口路径参数
int baudrate_ = 115200;    // 波特率参数
double scale_factor_ = 0.001;  // 单位转换系数（mN → N）

// 传感器状态机（修改：使用公开的rq_sensor_com接口，而非static函数）
static char sensor_state_machine()
{
    // 如果指定了串口，先设置全局串口路径，再调用自动扫描（适配原有逻辑）
    if (!serial_port_.empty())
    {
        RCLCPP_INFO(rclcpp::get_logger("robotiq_ft_sensor"), 
            "Trying to connect to sensor via serial port: %s (baudrate: %d)", 
            serial_port_.c_str(), baudrate_);
        
        // 调用公开的串口连接接口（自动扫描包含指定串口）
        char ret;
        if (ftdi_id.empty())
        {
            ret = rq_sensor_com();  // 自动扫描所有串口（包含指定的serial_port_）
        }
        else
        {
            ret = rq_sensor_com(ftdi_id);  // 指定serial_id扫描
        }
        return ret;
    }
    // 未指定串口，使用原有逻辑
    else
    {
        if (ftdi_id.empty())
        {
            return rq_sensor_state(max_retries_);
        }
        return rq_sensor_state(max_retries_, ftdi_id);
    }
}


/**
 * \brief 等待传感器连接（带日志）
 */
static void wait_for_other_connection(rclcpp::Node::SharedPtr node)
{
    char ret;
    while(rclcpp::ok())
    {
        RCLCPP_INFO(node->get_logger(), "Waiting for sensor connection... (serial_port: %s)", serial_port_.empty() ? "auto" : serial_port_.c_str());
        usleep(1000000);

        ret = sensor_state_machine();
        if(ret == 0)
        {
            RCLCPP_INFO(node->get_logger(), "Sensor connected successfully!");
            break;
        }

        rclcpp::spin_some(node);
    }
}

/**
 * \brief 获取传感器校准后的数据（单位转换）
 */
static void get_sensor_data(double* fx, double* fy, double* fz, double* mx, double* my, double* mz)
{
    // 读取原始数据（mN/mN·m）并转换为N/N·m
    *fx = rq_com_get_received_data(0) * scale_factor_;
    *fy = rq_com_get_received_data(1) * scale_factor_;
    *fz = rq_com_get_received_data(2) * scale_factor_;
    *mx = rq_com_get_received_data(3) * scale_factor_;
    *my = rq_com_get_received_data(4) * scale_factor_;
    *mz = rq_com_get_received_data(5) * scale_factor_;
}

/**
 * \brief 零点校准服务回调（修复：ROS2标准回调格式）
 */
void zero_calibration_callback(
    const std::shared_ptr<std_srvs::srv::Trigger::Request> req,
    std::shared_ptr<std_srvs::srv::Trigger::Response> res)
{
    rq_com_do_zero_force_flag();  // 直接调用底层校准函数
    res->success = true;
    res->message = "Sensor zero calibration done!";
    RCLCPP_INFO(rclcpp::get_logger("robotiq_ft_sensor"), "Zero calibration executed successfully");
}

int main(int argc, char **argv)
{
    // ROS 2节点初始化
    rclcpp::init(argc, argv);
    auto node = rclcpp::Node::make_shared("robotiq_ft_sensor");

    // 声明并获取参数（解决串口指定问题）
    node->declare_parameter<int>("max_retries", 100);
    node->declare_parameter<std::string>("serial_id", "");
    node->declare_parameter<std::string>("serial_port", "");  // 串口路径参数
    node->declare_parameter<int>("baudrate", 115200);         // 波特率参数
    node->declare_parameter<std::string>("frame_id", "robotiq_ft_frame_id");
    node->declare_parameter<double>("scale_factor", 0.001);   // 校准系数

    // 获取参数值
    node->get_parameter("max_retries", max_retries_);
    node->get_parameter("serial_id", ftdi_id);
    node->get_parameter("serial_port", serial_port_);
    node->get_parameter("baudrate", baudrate_);
    node->get_parameter("scale_factor", scale_factor_);

    // 打印参数信息（调试）
    RCLCPP_INFO(node->get_logger(), "Sensor node initialized with parameters:");
    RCLCPP_INFO(node->get_logger(), "  - serial_port: %s", serial_port_.c_str());
    RCLCPP_INFO(node->get_logger(), "  - baudrate: %d", baudrate_);
    RCLCPP_INFO(node->get_logger(), "  - max_retries: %d", max_retries_);

    // 尝试连接传感器
    char ret;
    ret = sensor_state_machine();
    if(ret == -1) wait_for_other_connection(node);
    ret = sensor_state_machine();
    if(ret == -1) wait_for_other_connection(node);
    ret = sensor_state_machine();
    if(ret == -1) wait_for_other_connection(node);

    // 创建发布者（标准WrenchStamped消息）
    auto wrench_pub = node->create_publisher<geometry_msgs::msg::WrenchStamped>("robotiq_ft_wrench", 512);

    // 创建零点校准服务（修复：使用std::bind绑定回调）
    auto zero_service = node->create_service<std_srvs::srv::Trigger>(
        "robotiq_ft_sensor/set_zero",
        std::bind(&zero_calibration_callback, std::placeholders::_1, std::placeholders::_2));

    // 初始化消息
    geometry_msgs::msg::WrenchStamped wrenchMsg;
    std::string frame_id;
    node->get_parameter("frame_id", frame_id);
    wrenchMsg.header.frame_id = frame_id;

    RCLCPP_INFO(node->get_logger(), "Starting FT300 sensor node (publishing to: /robotiq_ft_wrench)");
    RCLCPP_INFO(node->get_logger(), "Zero calibration service ready: /robotiq_ft_sensor/set_zero");
    
    // 主循环（发布数据）
    rclcpp::Rate rate(100);  // 100Hz发布频率
    while(rclcpp::ok())
    {
        ret = sensor_state_machine();
        if (ret == -1)
        {
            RCLCPP_WARN(node->get_logger(), "Sensor disconnected, reconnecting...");
            wait_for_other_connection(node);
        }

        if(rq_com_get_valid_stream())  // 修改：使用串口层的流验证
        {
            // 获取校准后的数据
            double fx, fy, fz, mx, my, mz;
            get_sensor_data(&fx, &fy, &fz, &mx, &my, &mz);

            if(rq_com_got_new_message())  // 修改：使用串口层的新消息判断
            {
                // 填充并发布消息
                wrenchMsg.header.stamp = node->get_clock()->now();
                wrenchMsg.wrench.force.x = fx;
                wrenchMsg.wrench.force.y = fy;
                wrenchMsg.wrench.force.z = fz;
                wrenchMsg.wrench.torque.x = mx;
                wrenchMsg.wrench.torque.y = my;
                wrenchMsg.wrench.torque.z = mz;
                wrench_pub->publish(wrenchMsg);
            }
        }

        rclcpp::spin_some(node);
        rate.sleep();
    }

    rclcpp::shutdown();
    return 0;
}
