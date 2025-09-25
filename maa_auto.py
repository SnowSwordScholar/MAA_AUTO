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
import re

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
        
        # 公招相关配置
        self.recruitment_command = self.config.get('Recruitment', 'command', fallback='cd /Task/MAA/Python && uv run python qwq.py -v')
        self.recruitment_interval_hours = float(self.config.get('Recruitment', 'interval_hours', fallback=9.5))
        self.senior_operator_keyword = self.config.get('Recruitment', 'senior_operator_keyword', fallback='资深干员')
        self.top_operator_keyword = self.config.get('Recruitment', 'top_operator_keyword', fallback='高级资深干员')
        
        # 公招相关状态
        self.last_recruitment_time = None
        
        # 从ADB命令中提取设备ID
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
        self.config['Recruitment'] = {
            'command': 'cd /Task/MAA/Python && uv run python qwq.py -v',
            'interval_hours': '9.5',
            'senior_operator_keyword': '资深干员',
            'top_operator_keyword': '高级资深干员'
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
        
    def wake_up_screen(self):
        """唤醒屏幕"""
        try:
            self.logger.info("尝试唤醒屏幕")
            
            # 发送唤醒按键
            wake_cmd = f"adb -s {self.adb_device} shell input keyevent KEYCODE_WAKEUP"
            result = subprocess.run(wake_cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self.logger.info("屏幕唤醒命令发送成功")
                # 等待屏幕唤醒
                time.sleep(2)
                
                # 发送菜单键解锁（如果需要）
                menu_cmd = f"adb -s {self.adb_device} shell input keyevent KEYCODE_MENU"
                subprocess.run(menu_cmd, shell=True, capture_output=True, timeout=10)
                
                return True
            else:
                self.logger.warning(f"屏幕唤醒命令失败: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"唤醒屏幕时发生错误: {e}")
            return False
    
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
            
    def should_run_recruitment(self):
        """检查是否应该执行公招（需要在任务时间段内且间隔足够）"""
        # 首先检查是否在任务时间段内
        if not self.is_in_run_time():
            return False
            
        if self.last_recruitment_time is None:
            return True
            
        now = datetime.now()
        time_since_last = now - self.last_recruitment_time
        interval_seconds = self.recruitment_interval_hours * 3600
        
        return time_since_last.total_seconds() >= interval_seconds
    
    def is_recruitment_due(self):
        """检查公招是否到期（不考虑时间段限制，用于显示状态）"""
        if self.last_recruitment_time is None:
            return True
            
        now = datetime.now()
        time_since_last = now - self.last_recruitment_time
        interval_seconds = self.recruitment_interval_hours * 3600
        
        return time_since_last.total_seconds() >= interval_seconds
    
    def run_recruitment_command(self):
        """执行公招命令（需要暂停MAA任务）"""
        # 如果MAA正在运行，先停止它
        maa_was_running = self.is_running
        if maa_was_running:
            self.logger.info("公招开始，暂停MAA肉鸽任务")
            self.stop_maa_command()
            # 等待MAA进程完全停止
            time.sleep(3)
        
        try:
            # 在执行公招前先启动明日方舟
            self.logger.info("公招任务启动前，先启动明日方舟")
            adb_success = self.run_adb_command()
            if not adb_success:
                self.logger.warning("启动明日方舟失败，但继续执行公招任务")
            else:
                # 等待游戏启动
                self.logger.info("等待明日方舟启动完成...")
                time.sleep(10)
            
            self.logger.info(f"开始执行公招命令: {self.recruitment_command}")
            
            # 执行公招命令，捕获所有输出到内存中
            result = subprocess.run(
                self.recruitment_command, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=1800  # 30分钟超时
            )
            
            # 记录公招执行时间
            self.last_recruitment_time = datetime.now()
            
            # 分析输出日志
            output_lines = result.stdout + result.stderr
            self.analyze_recruitment_output(output_lines)
            
            success = False
            if result.returncode == 0:
                self.logger.info("公招命令执行成功")
                success = True
            else:
                self.logger.error(f"公招命令执行失败，返回码: {result.returncode}")
                # 发送公招失败通知
                error_message = f"公招脚本执行失败，返回码: {result.returncode}\n错误输出: {result.stderr[:500]}"
                self.send_webhook_notification("公招脚本执行失败", error_message)
            
            # 公招结束后，如果之前MAA在运行且仍在任务时间段内，准备重启MAA
            if maa_was_running and self.is_in_run_time():
                self.logger.info("公招完成，准备恢复MAA肉鸽任务")
                # 给一点时间让系统稳定
                time.sleep(5)
            
            return success
                
        except subprocess.TimeoutExpired:
            self.logger.error("公招命令执行超时")
            error_message = "公招脚本执行超时（30分钟），可能脚本更新导致问题"
            self.send_webhook_notification("公招脚本执行超时", error_message)
            
            # 超时后也要考虑恢复MAA
            if maa_was_running and self.is_in_run_time():
                self.logger.info("公招超时，准备恢复MAA肉鸽任务")
                time.sleep(5)
            
            return False
        except Exception as e:
            self.logger.error(f"执行公招命令时发生错误: {e}")
            error_message = f"公招脚本执行出现异常: {str(e)}"
            self.send_webhook_notification("公招脚本执行异常", error_message)
            
            # 异常后也要考虑恢复MAA
            if maa_was_running and self.is_in_run_time():
                self.logger.info("公招异常，准备恢复MAA肉鸽任务")
                time.sleep(5)
            
            return False
    
    def analyze_recruitment_output(self, output):
        """分析公招输出日志，查找高级干员"""
        try:
            # 检查是否包含高级资深干员（六星）
            if self.top_operator_keyword in output:
                self.logger.info(f"检测到{self.top_operator_keyword}！")
                message = f"恭喜！检测到{self.top_operator_keyword}（六星）\n执行时间: {datetime.now()}"
                self.send_webhook_notification(f"🌟 {self.top_operator_keyword}出现！", message)
                return
            
            # 检查是否包含资深干员（五星）
            if self.senior_operator_keyword in output:
                self.logger.info(f"检测到{self.senior_operator_keyword}！")
                message = f"检测到{self.senior_operator_keyword}（五星）\n执行时间: {datetime.now()}"
                self.send_webhook_notification(f"⭐ {self.senior_operator_keyword}出现！", message)
                return
            
            self.logger.info("本次公招未检测到高级干员")
            
        except Exception as e:
            self.logger.error(f"分析公招输出时发生错误: {e}")
    
    def get_next_recruitment_time(self):
        """获取下次公招时间"""
        if self.last_recruitment_time is None:
            if self.is_in_run_time():
                return "立即执行"
            else:
                return "等待任务时间段"
                
        next_due_time = self.last_recruitment_time + timedelta(hours=self.recruitment_interval_hours)
        
        # 如果下次到期时间在任务时间段内，直接返回
        if self.is_time_in_run_period(next_due_time):
            return next_due_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 如果下次到期时间不在任务时间段内，计算下一个任务时间段开始时间
        actual_next_time = self.calculate_next_run_time_after(next_due_time)
        return f"{next_due_time.strftime('%Y-%m-%d %H:%M:%S')} (实际执行: {actual_next_time.strftime('%Y-%m-%d %H:%M:%S')})"
    
    def is_time_in_run_period(self, target_time):
        """检查指定时间是否在运行时间段内"""
        hour = target_time.hour
        if self.run_time_end > self.run_time_start:
            return self.run_time_start <= hour < self.run_time_end
        else:
            return hour >= self.run_time_start or hour < self.run_time_end
    
    def calculate_next_run_time_after(self, after_time):
        """计算指定时间之后的下一个运行时间段开始时间"""
        if after_time.hour < self.run_time_start:
            # 同一天的开始时间
            return after_time.replace(hour=self.run_time_start, minute=0, second=0, microsecond=0)
        else:
            # 下一天的开始时间
            next_day = after_time + timedelta(days=1)
            return next_day.replace(hour=self.run_time_start, minute=0, second=0, microsecond=0)
            
    def main_loop(self):
        """主循环"""
        self.logger.info("MAA自动任务启动")
        self.logger.info(f"任务时间段: {self.run_time_start}点 - {self.run_time_end}点")
        self.logger.info(f"公招任务间隔: {self.recruitment_interval_hours}小时")
        
        # 显示公招状态
        if self.is_recruitment_due():
            self.logger.info("公招已到期，等待任务时间段内执行")
        else:
            self.logger.info(f"下次公招时间: {self.get_next_recruitment_time()}")
        
        while True:
            try:
                # 检查任务时间段
                if not self.is_in_run_time():
                    delay = self.calculate_delay()
                    # 在暂停期间，每小时检查一次（但不执行任何任务）
                    wait_increment = min(3600, delay)
                    
                    # 显示公招状态（如果公招已到期）
                    if self.is_recruitment_due():
                        self.logger.info(f"公招已到期，等待任务时间段开始。还需等待{wait_increment}秒")
                    else:
                        self.logger.info(f"不在任务时间段，等待{wait_increment}秒后再次检查")
                    
                    time.sleep(wait_increment)
                    continue
                
                # 在任务时间段内，首先检查公招
                if self.should_run_recruitment():
                    self.logger.info("开始执行公招任务")
                    recruitment_success = self.run_recruitment_command()
                    if recruitment_success:
                        self.logger.info(f"公招任务执行成功，下次执行时间: {self.get_next_recruitment_time()}")
                    else:
                        self.logger.warning("公招任务执行失败")
                    
                    # 公招完成后，如果仍在任务时间段内，继续MAA任务
                    if not self.is_in_run_time():
                        self.logger.info("公招完成时已超出任务时间段，等待下次任务时间")
                        continue
                
                # 执行MAA任务流程
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
                    time.sleep(10)
                    continue
                
                # 等待游戏启动
                self.logger.info("等待游戏启动...")
                time.sleep(10)
                
                # 执行MAA命令
                maa_success = self.run_maa_command()
                
                # 更新错误计数
                self.update_error_count(maa_success)
                
                # 根据结果决定等待时间
                if maa_success:
                    wait_time = self.restart_delay
                    self.logger.info(f"MAA执行成功，等待 {wait_time} 秒后重试")
                else:
                    wait_time = min(self.restart_delay * 2, 300)
                    self.logger.warning(f"MAA执行失败，等待 {wait_time} 秒后重试")
                
                # 在等待期间检查公招和时间段
                start_wait = time.time()
                while time.time() - start_wait < wait_time:
                    remaining_wait = wait_time - (time.time() - start_wait)
                    sleep_time = min(30, remaining_wait)
                    
                    if sleep_time <= 0:
                        break
                        
                    time.sleep(sleep_time)
                    
                    # 检查是否还在任务时间段内
                    if not self.is_in_run_time():
                        self.logger.info("已超出任务时间段，停止当前等待")
                        break
                    
                    # 检查是否需要执行公招（这会中断当前MAA任务）
                    if self.should_run_recruitment():
                        self.logger.info("在等待期间触发公招任务，中断当前等待")
                        recruitment_success = self.run_recruitment_command()
                        if recruitment_success:
                            self.logger.info(f"公招任务执行成功，下次执行时间: {self.get_next_recruitment_time()}")
                        # 公招完成后跳出等待循环，重新开始MAA任务
                        break
                
            except KeyboardInterrupt:
                self.logger.info("用户中断程序")
                self.stop_maa_command()
                break
            except Exception as e:
                self.logger.error(f"主循环发生未知错误: {e}")
                self.stop_maa_command()
                time.sleep(60)

if __name__ == "__main__":
    # 设置信号处理
    def signal_handler(sig, frame):
        print("\n接收到中断信号，正在关闭...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    maa = MAAAuto()
    maa.main_loop()
