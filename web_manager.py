#!/usr/bin/env python3
"""
MAA自动化任务Web管理系统
提供Web界面来管理和监控MAA自动化进程
"""

import os
import sys
import json
import subprocess
import configparser
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import threading
import time
import logging
from pathlib import Path

# 获取当前脚本所在目录
SCRIPT_DIR = Path(__file__).parent.absolute()
CONFIG_FILE = SCRIPT_DIR / "config.ini"
LOG_FILE = SCRIPT_DIR / "logs" / "maa_auto.log"
WEB_LOG_FILE = SCRIPT_DIR / "logs" / "web_manager.log"

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(WEB_LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
app.secret_key = 'maa_web_manager_secret_key_2025'

class MAAWebManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.load_config()
        self.service_name = "maa-auto"
        
    def load_config(self):
        """加载配置文件"""
        try:
            self.config.read(CONFIG_FILE, encoding='utf-8')
            logging.info("配置文件加载成功")
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            
    def save_config(self):
        """保存配置文件"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logging.info("配置文件保存成功")
            return True
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")
            return False
            
    def get_service_status(self):
        """获取systemd服务状态"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', self.service_name],
                capture_output=True, text=True, timeout=10
            )
            is_active = result.stdout.strip() == 'active'
            
            # 获取详细状态信息
            result = subprocess.run(
                ['systemctl', 'status', self.service_name, '--no-pager'],
                capture_output=True, text=True, timeout=10
            )
            status_info = result.stdout
            
            return {
                'active': is_active,
                'status': 'running' if is_active else 'stopped',
                'details': status_info
            }
        except Exception as e:
            logging.error(f"获取服务状态失败: {e}")
            return {
                'active': False,
                'status': 'unknown',
                'details': f'Error: {e}'
            }
            
    def start_service(self):
        """启动MAA服务"""
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', 'start', self.service_name],
                capture_output=True, text=True, timeout=30
            )
            success = result.returncode == 0
            logging.info(f"启动服务: {'成功' if success else '失败'}")
            return success, result.stderr if not success else "服务启动成功"
        except Exception as e:
            logging.error(f"启动服务失败: {e}")
            return False, str(e)
            
    def stop_service(self):
        """停止MAA服务"""
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', 'stop', self.service_name],
                capture_output=True, text=True, timeout=30
            )
            success = result.returncode == 0
            logging.info(f"停止服务: {'成功' if success else '失败'}")
            return success, result.stderr if not success else "服务停止成功"
        except Exception as e:
            logging.error(f"停止服务失败: {e}")
            return False, str(e)
            
    def restart_service(self):
        """重启MAA服务"""
        try:
            result = subprocess.run(
                ['sudo', 'systemctl', 'restart', self.service_name],
                capture_output=True, text=True, timeout=30
            )
            success = result.returncode == 0
            logging.info(f"重启服务: {'成功' if success else '失败'}")
            return success, result.stderr if not success else "服务重启成功"
        except Exception as e:
            logging.error(f"重启服务失败: {e}")
            return False, str(e)
            
    def get_logs(self, lines=100):
        """获取MAA日志"""
        try:
            if LOG_FILE.exists():
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    return ''.join(all_lines[-lines:])
            else:
                return "日志文件不存在"
        except Exception as e:
            logging.error(f"读取日志失败: {e}")
            return f"读取日志失败: {e}"
            
    def execute_task_directly(self, task_type):
        """直接执行特定任务"""
        try:
            commands = {
                'recruitment': self.config.get('Recruitment', 'command', fallback=''),
                'clear_stamina': self.config.get('DailyTasks', 'start_day_command', fallback=''),
                'clear_materials': self.config.get('DailyTasks', 'end_day_command', fallback=''),
                'baah': self.config.get('BAAH', 'command', fallback=''),
                'maa_roguelike': self.config.get('MAA', 'maa_command', fallback='')
            }
            
            if task_type not in commands or not commands[task_type]:
                return False, f"未找到任务类型: {task_type}"
                
            # 先执行ADB命令（如果需要）
            if task_type in ['recruitment', 'clear_stamina', 'clear_materials', 'maa_roguelike']:
                adb_command = self.config.get('MAA', 'adb_command', fallback='')
                if adb_command:
                    subprocess.run(adb_command, shell=True, timeout=30)
                    
            # 执行任务命令
            result = subprocess.run(
                commands[task_type],
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            success = result.returncode == 0
            output = result.stdout + result.stderr
            
            logging.info(f"直接执行任务{task_type}: {'成功' if success else '失败'}")
            return success, output
            
        except Exception as e:
            logging.error(f"执行任务{task_type}失败: {e}")
            return False, str(e)

# 全局管理器实例
manager = MAAWebManager()

@app.route('/')
def index():
    """主页"""
    status = manager.get_service_status()
    return render_template('index.html', status=status)

@app.route('/api/status')
def api_status():
    """API: 获取服务状态"""
    return jsonify(manager.get_service_status())

@app.route('/api/service/<action>', methods=['POST'])
def api_service_control(action):
    """API: 控制服务"""
    if action == 'start':
        success, message = manager.start_service()
    elif action == 'stop':
        success, message = manager.stop_service()
    elif action == 'restart':
        success, message = manager.restart_service()
    else:
        return jsonify({'success': False, 'message': '无效的操作'})
        
    return jsonify({'success': success, 'message': message})

@app.route('/config')
def config_page():
    """配置页面"""
    return render_template('config.html', config=manager.config)

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """API: 配置管理"""
    if request.method == 'GET':
        # 返回配置数据
        config_dict = {}
        for section in manager.config.sections():
            config_dict[section] = dict(manager.config[section])
        return jsonify(config_dict)
        
    elif request.method == 'POST':
        # 更新配置
        try:
            data = request.json
            for section, options in data.items():
                if not manager.config.has_section(section):
                    manager.config.add_section(section)
                for key, value in options.items():
                    manager.config.set(section, key, str(value))
                    
            success = manager.save_config()
            return jsonify({'success': success, 'message': '配置保存成功' if success else '配置保存失败'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'配置更新失败: {e}'})

@app.route('/logs')
def logs_page():
    """日志页面"""
    return render_template('logs.html')

@app.route('/api/logs')
def api_logs():
    """API: 获取日志"""
    lines = request.args.get('lines', 100, type=int)
    logs = manager.get_logs(lines)
    return jsonify({'logs': logs})

@app.route('/tasks')
def tasks_page():
    """任务页面"""
    return render_template('tasks.html')

@app.route('/api/task/<task_type>', methods=['POST'])
def api_execute_task(task_type):
    """API: 执行任务"""
    success, output = manager.execute_task_directly(task_type)
    return jsonify({
        'success': success,
        'output': output,
        'task_type': task_type
    })

if __name__ == '__main__':
    # 确保日志目录存在
    (SCRIPT_DIR / "logs").mkdir(exist_ok=True)
    
    # 启动Web服务器
    logging.info("MAA Web管理器启动")
    app.run(host='0.0.0.0', port=5000, debug=False)