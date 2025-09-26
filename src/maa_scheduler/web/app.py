"""
MAA任务调度器Web界面
支持暗黑模式和中英文切换
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pathlib import Path
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.maa_scheduler.core.scheduler_new import TaskScheduler
from src.maa_scheduler.core.config_new import ConfigManager

class WebManager:
    """Web管理界面"""
    
    def __init__(self, config_file: str = "task_config.ini"):
        self.app = Flask(__name__, 
                        template_folder=str(Path(__file__).parent / "templates"),
                        static_folder=str(Path(__file__).parent / "static"))
        
        # 配置
        self.app.secret_key = os.getenv('WEB_SECRET_KEY', 'maa_web_secret_2025')
        self.config_file = config_file
        self.scheduler = None
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 注册路由
        self.setup_routes()
        
    def setup_routes(self):
        """设置路由"""
        
        @self.app.route('/')
        def index():
            """主页"""
            return render_template('index.html')
            
        @self.app.route('/api/tasks')
        def api_tasks():
            """获取任务列表API"""
            try:
                config = ConfigManager(self.config_file)
                flows = config.get_task_flows()
                payloads = config.get_task_payloads()
                
                tasks = []
                for task_name, flow in flows.items():
                    task_info = {
                        'name': task_name,
                        'type': flow['type'],
                        'time_params': flow['time_params'],
                        'priority': flow['priority'],
                        'random_range': flow['random_range'],
                        'queue_group': flow['queue_group'],
                        'trigger_condition': flow['trigger_condition'],
                        'payload_count': len(payloads.get(task_name, [])),
                        'status': 'idle'  # TODO: 获取实际状态
                    }
                    tasks.append(task_info)
                
                return jsonify({
                    'success': True,
                    'tasks': tasks,
                    'total': len(tasks)
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
                
        @self.app.route('/api/task/<task_name>')
        def api_task_detail(task_name):
            """获取任务详情API"""
            try:
                config = ConfigManager(self.config_file)
                flows = config.get_task_flows()
                payloads = config.get_task_payloads()
                keywords = config.get_task_keywords()
                
                if task_name not in flows:
                    return jsonify({
                        'success': False,
                        'error': 'Task not found'
                    }), 404
                
                task_detail = {
                    'name': task_name,
                    'flow': flows[task_name],
                    'payloads': payloads.get(task_name, []),
                    'keywords': keywords.get(task_name, {}),
                    'status': 'idle'  # TODO: 获取实际状态
                }
                
                return jsonify({
                    'success': True,
                    'task': task_detail
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
                
        @self.app.route('/api/scheduler/status')
        def api_scheduler_status():
            """获取调度器状态API"""
            try:
                # TODO: 获取实际调度器状态
                return jsonify({
                    'success': True,
                    'status': {
                        'running': False,
                        'uptime': 0,
                        'total_tasks': 0,
                        'active_tasks': 0,
                        'completed_tasks': 0,
                        'failed_tasks': 0
                    }
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
                
        @self.app.route('/api/logs')
        def api_logs():
            """获取日志API"""
            try:
                log_file = Path.cwd() / "logs" / "maa_scheduler.log"
                if not log_file.exists():
                    return jsonify({
                        'success': True,
                        'logs': []
                    })
                
                # 读取最后100行日志
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                logs = []
                for line in recent_lines:
                    line = line.strip()
                    if line:
                        logs.append({
                            'timestamp': datetime.now().isoformat(),
                            'message': line
                        })
                
                return jsonify({
                    'success': True,
                    'logs': logs
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
                
        @self.app.route('/api/settings')
        def api_settings():
            """获取系统设置API"""
            try:
                config = ConfigManager(self.config_file)
                
                # 获取系统设置
                settings = {
                    'log_level': config.get_system_setting('log_level', 'INFO'),
                    'max_concurrent_tasks': config.get_system_setting('max_concurrent_tasks', '3'),
                    'task_timeout_default': config.get_system_setting('task_timeout_default', '1800'),
                    'error_retry_count': config.get_system_setting('error_retry_count', '3'),
                    'error_retry_delay': config.get_system_setting('error_retry_delay', '60'),
                    'web_host': config.get_system_setting('web_host', '0.0.0.0'),
                    'web_port': config.get_system_setting('web_port', '5000'),
                    'web_debug': config.get_system_setting('web_debug', 'false'),
                    'web_theme': config.get_system_setting('web_theme', 'auto'),
                    'web_language': config.get_system_setting('web_language', 'auto')
                }
                
                return jsonify({
                    'success': True,
                    'settings': settings
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
                
        @self.app.route('/api/user/preferences', methods=['GET', 'POST'])
        def api_user_preferences():
            """用户偏好设置API"""
            if request.method == 'GET':
                return jsonify({
                    'success': True,
                    'preferences': {
                        'theme': session.get('theme', 'auto'),
                        'language': session.get('language', 'auto')
                    }
                })
            
            elif request.method == 'POST':
                data = request.get_json()
                if 'theme' in data:
                    session['theme'] = data['theme']
                if 'language' in data:
                    session['language'] = data['language']
                
                return jsonify({
                    'success': True,
                    'message': 'Preferences updated'
                })
                
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """运行Web服务器"""
        self.logger.info(f"启动Web管理界面: http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='MAA任务调度器Web界面')
    parser.add_argument('--config', '-c', 
                       default='task_config.ini',
                       help='配置文件路径')
    parser.add_argument('--host', 
                       default='0.0.0.0',
                       help='Web服务器地址')
    parser.add_argument('--port', '-p',
                       type=int,
                       default=5000,
                       help='Web服务器端口')
    parser.add_argument('--debug', '-d',
                       action='store_true',
                       help='调试模式')
    
    args = parser.parse_args()
    
    web_manager = WebManager(args.config)
    web_manager.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()