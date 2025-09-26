"""
任务配置管理器
"""

import configparser
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """初始化配置管理器"""
        # 如果未提供配置文件路径，使用默认路径
        if config_file is None:
            current_dir = Path.cwd()
            self.config_file = str(current_dir / "task_config.ini")
        else:
            self.config_file = str(Path(config_file))
            
        # 加载环境变量
        config_path = Path(self.config_file)
        env_file = config_path.parent / ".env"
        if env_file.exists():
            load_dotenv(str(env_file))
            
        self.config = configparser.ConfigParser()
        self.load_config()
        
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            config_path = Path(self.config_file)
            if config_path.exists():
                self.config.read(self.config_file, encoding='utf-8')
            else:
                # 创建默认配置
                self._create_default_config()
                self.save_config()
            return True
        except Exception:
            return False
            
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            return True
        except Exception:
            return False
            
    def _create_default_config(self) -> None:
        """创建默认配置"""
        # 创建基本配置节
        for section in ['TaskSchedule', 'TaskDefinitions', 'TaskKeywords', 'WebhookTemplates', 'SystemSettings']:
            if not self.config.has_section(section):
                self.config.add_section(section)
                
        # 设置默认系统设置
        defaults = {
            'log_level': 'INFO',
            'max_concurrent_tasks': '3',
            'task_timeout_default': '1800',
            'adb_device': 'localhost:35555',
            'error_retry_count': '3',
            'error_retry_delay': '60',
            'web_host': '0.0.0.0',
            'web_port': '5000',
            'web_debug': 'false',
            'web_theme': 'auto',
            'web_language': 'auto'
        }
        
        for key, value in defaults.items():
            self.config.set('SystemSettings', key, value)
            
        self.save_config()
        
    def get_task_schedules(self) -> Dict[str, Dict[str, Any]]:
        """获取任务调度配置"""
        schedules = {}
        if self.config.has_section('TaskSchedule'):
            for task_name, schedule_str in self.config['TaskSchedule'].items():
                parts = schedule_str.split('|')
                if len(parts) >= 5:
                    schedules[task_name] = {
                        'type': parts[0],
                        'time_params': parts[1],
                        'priority': int(parts[2]),
                        'random_range': parts[3],
                        'queue_group': parts[4]
                    }
        return schedules
        
    def get_task_definitions(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取任务定义"""
        definitions = {}
        if self.config.has_section('TaskDefinitions'):
            # 按任务名分组步骤
            task_steps = {}
            for key, value in self.config['TaskDefinitions'].items():
                if '.' in key:
                    task_name, step_num = key.rsplit('.', 1)
                    if task_name not in task_steps:
                        task_steps[task_name] = {}
                    task_steps[task_name][int(step_num)] = value
            
            # 整理步骤
            for task_name, steps_dict in task_steps.items():
                steps = []
                for step_num in sorted(steps_dict.keys()):
                    step_str = steps_dict[step_num]
                    step_data = self._parse_step_definition(step_str)
                    if step_data:
                        step_data['step_num'] = step_num
                        steps.append(step_data)
                if steps:
                    definitions[task_name] = steps
                    
        return definitions
        
    def _parse_step_definition(self, step_str: str) -> Optional[Dict[str, Any]]:
        """解析步骤定义"""
        try:
            parts = step_str.split(':', 2)
            if len(parts) < 2:
                return None
                
            step_type = parts[0]
            params = parts[1].split(':') if parts[1] else []
            
            # 解析选项
            options = {}
            if len(parts) > 2 and parts[2]:
                for option in parts[2].split(','):
                    if '=' in option:
                        key, value = option.split('=', 1)
                        # 转换值类型
                        if value.lower() in ('true', 'false'):
                            value = value.lower() == 'true'
                        elif value.isdigit():
                            value = int(value)
                        options[key.strip()] = value
            
            return {
                'type': step_type,
                'params': params,
                'options': options
            }
        except Exception:
            return None
            
    def get_task_keywords(self) -> Dict[str, Dict[str, Any]]:
        """获取任务关键词配置"""
        keywords = {}
        if self.config.has_section('TaskKeywords'):
            for key, value in self.config['TaskKeywords'].items():
                if '.' in key:
                    task_name, keyword_type = key.rsplit('.', 1)
                    if task_name not in keywords:
                        keywords[task_name] = {}
                    
                    keywords_str, action = value.split(':', 1)
                    keyword_list = [k.strip() for k in keywords_str.split(',')]
                    keywords[task_name][keyword_type] = {
                        'keywords': keyword_list,
                        'action': action
                    }
        return keywords
        
    def get_webhook_templates(self) -> Dict[str, Dict[str, str]]:
        """获取WebHook模板"""
        templates = {}
        if self.config.has_section('WebhookTemplates'):
            for template_name, template_str in self.config['WebhookTemplates'].items():
                parts = template_str.split(':', 2)
                if len(parts) >= 3:
                    templates[template_name] = {
                        'title': parts[0],
                        'description': parts[1],
                        'tags': parts[2]
                    }
        return templates
        
    def get_system_setting(self, key: str, default: Any = None) -> Any:
        """获取系统设置"""
        if self.config.has_section('SystemSettings'):
            return self.config.get('SystemSettings', key, fallback=default)
        return default
        
    def get_env(self, key: str, default: str = "") -> str:
        """获取环境变量"""
        return os.getenv(key, default)
        
    def add_task_schedule(self, task_name: str, schedule_config: str) -> bool:
        """添加任务调度"""
        if not self.config.has_section('TaskSchedule'):
            self.config.add_section('TaskSchedule')
        
        self.config.set('TaskSchedule', task_name, schedule_config)
        return self.save_config()
        
    def add_task_definition(self, task_name: str, step_definitions: List[str]) -> bool:
        """添加任务定义"""
        if not self.config.has_section('TaskDefinitions'):
            self.config.add_section('TaskDefinitions')
        
        # 删除现有的步骤定义
        keys_to_remove = [key for key in self.config['TaskDefinitions'].keys() 
                         if key.startswith(f"{task_name}.")]
        for key in keys_to_remove:
            self.config.remove_option('TaskDefinitions', key)
        
        # 添加新的步骤定义
        for i, step_def in enumerate(step_definitions, 1):
            self.config.set('TaskDefinitions', f"{task_name}.{i}", step_def)
        
        return self.save_config()
        
    def remove_task(self, task_name: str) -> bool:
        """删除任务"""
        modified = False
        
        # 从调度中删除
        if self.config.has_section('TaskSchedule') and self.config.has_option('TaskSchedule', task_name):
            self.config.remove_option('TaskSchedule', task_name)
            modified = True
        
        # 从定义中删除
        if self.config.has_section('TaskDefinitions'):
            keys_to_remove = [key for key in self.config['TaskDefinitions'].keys() 
                             if key.startswith(f"{task_name}.")]
            for key in keys_to_remove:
                self.config.remove_option('TaskDefinitions', key)
                modified = True
        
        # 从关键词配置中删除
        if self.config.has_section('TaskKeywords'):
            keys_to_remove = [key for key in self.config['TaskKeywords'].keys() 
                             if key.startswith(f"{task_name}.")]
            for key in keys_to_remove:
                self.config.remove_option('TaskKeywords', key)
                modified = True
        
        return self.save_config() if modified else True