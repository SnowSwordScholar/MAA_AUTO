#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import subprocess
import logging
import configparser
import threading
from datetime import datetime, timedelta
import requests
import signal

class MAAAuto:
    def __init__(self, config_file="/Task/MAA_Auto/config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
        # 错误计数
        self.error_count = 0
        self.last_error_time = None
        
        # MAA进程控制
        self.maa_process = None
        self.is_running = False
        
        # ADB设备信息
        self.adb_device = 'localhost:35555'  # 默认设备
        
        # 设置日志
        self.setup_logging()
        
        # 加载配置 (在日志设置之后)
        self.load_config()
        
    def load_config(self):
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            self.create_default_config()
        
        self.config.read(self.config_file)
        
        # 读取配置
        self.adb_command = self.config.get('MAA', 'adb_command', fallback='adb connect localhost:35555 ; adb -s localhost:35555 shell am start -n com.hypergryph.arknights/com.u8.sdk.U8UnityContext')
        self.maa_command = self.config.get('MAA', 'maa_command', fallback='maa roguelike Sami -v')
        self.maa_timeout = int(self.config.get('MAA', 'maa_timeout', fallback=3600))  # 默认1小时超时
        self.run_time_start = int(self.config.get('Schedule', 'run_time_start', fallback=23))
        self.run_time_end = int(self.config.get('Schedule', 'run_time_end', fallback=11))
        self.restart_delay = int(self.config.get('Schedule', 'restart_delay', fallback=60))
        self.max_errors = int(self.config.get('Error', 'max_errors', fallback=3))
        self.error_window = int(self.config.get('Error', 'error_window', fallback=600))
        self.webhook_url = self.config.get('Notification', 'webhook_url', fallback='')
        
        # 从ADB命令中提取设备ID
        import re
        adb_device_match = re.search(r'adb -s ([^ ]+)', self.adb_command)
        if adb_device_match:
            self.adb_device = adb_device_match.group(1)
            self.logger.info(f"从配置中提取ADB设备ID: {self.adb_device}")
        
    def create_default_config(self):
        """创建默认配置文件"""
        self.config['MAA'] = {
            'adb_command': 'adb -s localhost:35555 shell am start -n com.hypergryph.arknights/com.u8.sdk.U8UnityContext',
            'maa_command': 'maa roguelike Sami -v',
            'maa_timeout': '3600'
        }
        self.config['Schedule'] = {
            'run_time_start': '23',
            'run_time_end': '11',
            'restart_delay': '60'
        }
        self.config['Error'] = {
            'max_errors': '3',
            'error_window': '600'
        }
        self.config['Notification'] = {
            'webhook_url': 'https://<uid>.push.ft07.com/send/<sendkey>.send?title={title}&desp={desp}&tags=MAA'
        }
        
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            self.config.write(f)
            
    def setup_logging(self):
        """设置日志"""
        log_dir = "/Task/MAA_Auto/logs"
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'maa_auto.log')),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def is_in_run_time(self):
        """检查当前时间是否在运行时间段内"""
        now = datetime.now()
        current_hour = now.hour

        if self.run_time_end > self.run_time_start:
            # 正常时间段，如 8-18点
            return self.run_time_start <= current_hour < self.run_time_end
        else:
            # 跨天时间段，如 23-11点
            return current_hour >= self.run_time_start or current_hour < self.run_time_end
            
    def calculate_delay(self):
        """计算需要延迟的时间"""
        now = datetime.now()
        
        if not self.is_in_run_time():
            # 不在运行时间段，计算到下一个运行时间段开始的时间
            if now.hour < self.run_time_start:
                # 今天还没到开始时间
                target_time = now.replace(hour=self.run_time_start, minute=0, second=0, microsecond=0)
            else:
                # 已经过了开始时间，等到明天
                target_time = (now + timedelta(days=1)).replace(
                    hour=self.run_time_start, minute=0, second=0, microsecond=0
                )
            
            delay_seconds = (target_time - now).total_seconds()
            self.logger.info(f"不在运行时间段，延迟 {delay_seconds:.0f} 秒到 {target_time}")
            return delay_seconds
            
        return 0
        
    def run_adb_command(self):
        """执行ADB启动命令"""
        try:
            self.logger.info(f"执行ADB命令: {self.adb_command}")
            
            result = subprocess.run(self.adb_command, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.logger.error(f"ADB命令执行失败: {self.adb_command}")
                self.logger.error(f"错误输出: {result.stderr}")
                return False
            
            self.logger.info(f"ADB命令输出: {result.stdout}")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("ADB命令执行超时")
            return False
        except Exception as e:
            self.logger.error(f"执行ADB命令时发生错误: {e}")
            return False
    
    def run_maa_command(self):
        """执行MAA命令（长时间运行）"""
        try:
            self.logger.info(f"启动MAA命令: {self.maa_command}")
            
            # 启动MAA进程
            self.maa_process = subprocess.Popen(
                self.maa_command, 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid  # 创建新的进程组
            )
            
            self.is_running = True
            
            # 启动线程来读取输出
            stdout_thread = threading.Thread(target=self.read_output, args=(self.maa_process.stdout, "STDOUT"))
            stderr_thread = threading.Thread(target=self.read_output, args=(self.maa_process.stderr, "STDERR"))
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            
            stdout_thread.start()
            stderr_thread.start()
            
            # 等待进程结束或超时
            start_time = time.time()
            while self.is_running:
                try:
                    return_code = self.maa_process.poll()
                    if return_code is not None:
                        # 进程已结束
                        self.logger.info(f"MAA进程结束，返回码: {return_code}")
                        self.is_running = False
                        return return_code == 0
                    
                    # 检查超时
                    if time.time() - start_time > self.maa_timeout:
                        self.logger.warning(f"MAA命令运行超时（{self.maa_timeout}秒），终止进程")
                        self.stop_maa_command()
                        return False
                    
                    time.sleep(1)
                    
                except KeyboardInterrupt:
                    self.logger.info("用户中断MAA进程")
                    self.stop_maa_command()
                    return False
                    
        except Exception as e:
            self.logger.error(f"启动MAA命令时发生错误: {e}")
            return False
    
    def read_output(self, pipe, pipe_name):
        """读取进程输出"""
        try:
            for line in iter(pipe.readline, ''):
                if line.strip():
                    self.logger.info(f"MAA {pipe_name}: {line.strip()}")
        except Exception as e:
            self.logger.error(f"读取{pipe_name}时发生错误: {e}")
    
    def stop_maa_command(self):
        """停止MAA命令"""
        if self.maa_process and self.is_running:
            try:
                # 发送信号终止整个进程组
                os.killpg(os.getpgid(self.maa_process.pid), signal.SIGTERM)
                self.maa_process.wait(timeout=10)
                self.logger.info("MAA进程已终止")
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self.maa_process.pid), signal.SIGKILL)
                self.logger.warning("强制终止MAA进程")
            except Exception as e:
                self.logger.error(f"终止MAA进程时发生错误: {e}")
            finally:
                self.is_running = False
                self.maa_process = None
    
    def check_adb_connection(self):
        """检查ADB连接状态"""
        try:
            self.logger.info(f"检查ADB连接状态: {self.adb_device}")
            
            # 执行adb devices命令
            result = subprocess.run(f"adb devices", shell=True, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.logger.error("ADB命令执行失败")
                return False
                
            # 检查设备是否在列表中
            device_found = False
            for line in result.stdout.splitlines():
                if self.adb_device in line and not "offline" in line and not "unauthorized" in line:
                    if "device" in line:  # 确保设备状态为"device"，而不是"offline"或"unauthorized"
                        device_found = True
                        break
            
            if not device_found:
                self.logger.error(f"ADB设备 {self.adb_device} 未连接或状态异常")
                return False
            
            # 验证ADB连接是否可用（通过获取设备属性）
            check_cmd = f"adb -s {self.adb_device} shell getprop ro.product.model"
            check_result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if check_result.returncode != 0 or not check_result.stdout.strip():
                self.logger.error(f"ADB设备 {self.adb_device} 连接异常")
                return False
                
            self.logger.info(f"ADB设备 {self.adb_device} 连接正常: {check_result.stdout.strip()}")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("检查ADB连接超时")
            return False
        except Exception as e:
            self.logger.error(f"检查ADB连接时发生错误: {e}")
            return False
    
    def kill_arknights_process(self):
        """杀死明日方舟进程"""
        try:
            self.logger.info("尝试关闭明日方舟进程")
            
            # 使用ADB发送命令杀死明日方舟进程
            kill_cmd = f"adb -s {self.adb_device} shell am force-stop com.hypergryph.arknights"
            result = subprocess.run(kill_cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                self.logger.error(f"关闭明日方舟进程失败: {result.stderr}")
                return False
                
            self.logger.info("已关闭明日方舟进程")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("关闭明日方舟进程超时")
            return False
        except Exception as e:
            self.logger.error(f"关闭明日方舟进程时发生错误: {e}")
            return False
    
    def reconnect_adb(self):
        """重新连接ADB设备"""
        try:
            self.logger.info(f"尝试重新连接ADB设备: {self.adb_device}")
            
            # 首先断开连接
            disconnect_cmd = f"adb disconnect {self.adb_device}"
            subprocess.run(disconnect_cmd, shell=True, capture_output=True, timeout=10)
            
            # 然后重新连接
            connect_cmd = f"adb connect {self.adb_device}"
            result = subprocess.run(connect_cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if "connected" in result.stdout.lower():
                self.logger.info(f"ADB设备 {self.adb_device} 已重新连接")
                return True
            else:
                self.logger.error(f"重新连接ADB设备失败: {result.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("重新连接ADB设备超时")
            return False
        except Exception as e:
            self.logger.error(f"重新连接ADB设备时发生错误: {e}")
            return False
    
    def send_webhook_notification(self, title, message):
        """发送WebHook通知"""
        if not self.webhook_url or '<uid>' in self.webhook_url or '<sendkey>' in self.webhook_url:
            self.logger.warning("WebHook URL未配置或配置不完整")
            return
            
        try:
            # URL编码处理
            import urllib.parse
            encoded_title = urllib.parse.quote(title)
            encoded_message = urllib.parse.quote(message)
            
            url = self.webhook_url.format(title=encoded_title, desp=encoded_message)
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("WebHook通知发送成功")
            else:
                self.logger.warning(f"WebHook通知发送失败: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"发送WebHook通知时发生错误: {e}")
            
    def update_error_count(self, success):
        """更新错误计数"""
        now = time.time()
        
        if not success:
            # 记录错误
            if self.last_error_time and (now - self.last_error_time) > self.error_window:
                # 超过时间窗口，重置计数
                self.error_count = 1
            else:
                self.error_count += 1
                
            self.last_error_time = now
            
            # 检查是否达到错误阈值
            if self.error_count >= self.max_errors:
                # 先检查ADB连接是否正常
                adb_status = self.check_adb_connection()
                
                if not adb_status:
                    # ADB连接异常，发送特定通知
                    message = f"MAA自动任务在{self.error_window}秒内出现{self.error_count}次错误，ADB连接异常，时间: {datetime.fromtimestamp(now)}"
                    self.send_webhook_notification("MAA任务ADB连接错误", message)
                    
                    # 尝试重新连接ADB
                    self.logger.info("尝试重新连接ADB...")
                    reconnect_success = self.reconnect_adb()
                    
                    if reconnect_success:
                        # 杀死明日方舟进程并等待
                        self.kill_arknights_process()
                        self.logger.info("等待10秒后重新开始...")
                        time.sleep(10)
                else:
                    # ADB连接正常，但可能游戏进程出现问题
                    message = f"MAA自动任务在{self.error_window}秒内出现{self.error_count}次错误，最后一次错误时间: {datetime.fromtimestamp(now)}"
                    self.send_webhook_notification("MAA任务错误警报", message)
                    
                    # 尝试杀死并重启明日方舟
                    self.logger.info("尝试关闭并重启明日方舟...")
                    self.kill_arknights_process()
                    self.logger.info("等待10秒后重新开始...")
                    time.sleep(10)
                
                self.error_count = 0  # 重置计数
                
        else:
            # 成功执行，重置错误计数
            self.error_count = 0
            self.last_error_time = None
            
    def main_loop(self):
        """主循环"""
        self.logger.info("MAA自动任务启动")
        
        while True:
            try:
                # 检查是否需要延迟
                delay = self.calculate_delay()
                if delay > 0:
                    time.sleep(delay)
                    continue
                
                # 执行ADB命令启动游戏
                adb_success = self.run_adb_command()
                if not adb_success:
                    self.logger.error("ADB启动失败，检查ADB连接状态")
                    
                    # 检查ADB连接
                    adb_connection = self.check_adb_connection()
                    if not adb_connection:
                        self.logger.error("ADB连接异常，尝试重新连接")
                        self.reconnect_adb()
                    else:
                        self.logger.info("ADB连接正常，尝试杀死明日方舟进程")
                        self.kill_arknights_process()
                        
                    self.update_error_count(False)
                    self.logger.info("等待10秒后重试...")
                    time.sleep(10)  # 等待10秒后重试
                    continue
                
                # 等待游戏启动
                self.logger.info("等待游戏启动...")
                time.sleep(10)  # 等待10秒让游戏完全启动
                
                # 执行MAA命令
                maa_success = self.run_maa_command()
                
                # 更新错误计数
                self.update_error_count(maa_success)
                
                # 根据结果决定等待时间
                if maa_success:
                    wait_time = self.restart_delay
                    self.logger.info(f"MAA执行成功，等待 {wait_time} 秒后重试")
                else:
                    wait_time = min(self.restart_delay * 2, 300)  # 失败时等待时间加倍，最多5分钟
                    self.logger.warning(f"MAA执行失败，等待 {wait_time} 秒后重试")
                
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                self.logger.info("用户中断程序")
                self.stop_maa_command()
                break
            except Exception as e:
                self.logger.error(f"主循环发生未知错误: {e}")
                self.stop_maa_command()
                time.sleep(60)  # 发生未知错误时等待1分钟

if __name__ == "__main__":
    # 设置信号处理
    def signal_handler(sig, frame):
        print("\n接收到中断信号，正在关闭...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    maa = MAAAuto()
    maa.main_loop()
