"""
更新后的配置管理器 - 支持新的任务流程表格式
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import configparser
from dotenv import load_dotenv

class ConfigManager:
    """配置管理器 - 支持新的任务流程表格式"""
    
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
        self.logger = logging.getLogger(__name__)
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
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            return False
            
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            return True
        except Exception as e:
            self.logger.error(f"配置保存失败: {e}")
            return False
            
    def _create_default_config(self) -> None:
        """创建默认配置"""
        # 创建基本配置节
        for section in ['TaskFlow', 'TaskPayloads', 'TaskKeywords', 'WebhookTemplates', 'SystemSettings']:
            if not self.config.has_section(section):
                self.config.add_section(section)
                
    def get_task_flows(self) -> Dict[str, Dict[str, Any]]:
        """获取任务流程配置"""
        flows = {}
        if self.config.has_section('TaskFlow'):
            for task_name, flow_str in self.config['TaskFlow'].items():
                parts = flow_str.split('|')
                if len(parts) >= 6:
                    flows[task_name] = {
                        'type': parts[0],           # timewindow/interval
                        'time_params': parts[1],    # 时间参数
                        'priority': int(parts[2]),  # 优先级
                        'random_range': parts[3],   # 随机延迟范围
                        'queue_group': parts[4],    # 队列组
                        'trigger_condition': parts[5] # 条件触发
                    }
        return flows
        
    def get_task_payloads(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取任务负载配置"""
        payloads = {}
        if self.config.has_section('TaskPayloads'):
            # 按任务名分组步骤
            task_steps = {}
            for key, value in self.config['TaskPayloads'].items():
                if '.' in key:
                    task_name, step_num = key.rsplit('.', 1)
                    if task_name not in task_steps:
                        task_steps[task_name] = {}
                    try:
                        # 解析JSON格式的步骤定义
                        step_data = json.loads(value)
                        task_steps[task_name][int(step_num)] = step_data
                    except (json.JSONDecodeError, ValueError) as e:
                        self.logger.error(f"解析步骤定义失败 {key}: {e}")
            
            # 整理步骤
            for task_name, steps_dict in task_steps.items():
                steps = []
                for step_num in sorted(steps_dict.keys()):
                    step_data = steps_dict[step_num]
                    # 处理环境变量替换
                    step_data = self._replace_env_vars(step_data)
                    steps.append(step_data)
                payloads[task_name] = steps
                
        return payloads
        
    def get_task_keywords(self) -> Dict[str, Dict[str, Any]]:
        """获取任务关键词配置"""
        keywords = {}
        if self.config.has_section('TaskKeywords'):
            for task_name, keywords_str in self.config['TaskKeywords'].items():
                try:
                    # 解析JSON格式的关键词配置
                    keywords_data = json.loads(keywords_str)
                    keywords[task_name] = keywords_data
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析关键词配置失败 {task_name}: {e}")
        return keywords
        
    def get_webhook_templates(self) -> Dict[str, Dict[str, Any]]:
        """获取WebHook模板配置"""
        templates = {}
        if self.config.has_section('WebhookTemplates'):
            for template_name, template_str in self.config['WebhookTemplates'].items():
                try:
                    # 解析JSON格式的模板配置
                    template_data = json.loads(template_str)
                    # 处理环境变量替换
                    template_data = self._replace_env_vars(template_data)
                    templates[template_name] = template_data
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析WebHook模板失败 {template_name}: {e}")
        return templates
        
    def get_system_setting(self, key: str, default: Any = None) -> Any:
        """获取系统设置"""
        if self.config.has_section('SystemSettings'):
            return self.config.get('SystemSettings', key, fallback=default)
        return default
        
    def get_env(self, key: str, default: str = "") -> str:
        """获取环境变量"""
        return os.getenv(key, default)
        
    def _replace_env_vars(self, data: Any) -> Any:
        """递归替换环境变量"""
        if isinstance(data, str):
            # 替换${VAR_NAME}格式的环境变量
            if data.startswith('${') and data.endswith('}'):
                var_name = data[2:-1]
                return self.get_env(var_name, data)
            return data
        elif isinstance(data, dict):
            return {k: self._replace_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_env_vars(item) for item in data]
        else:
            return data
            
    def add_task_flow(self, task_name: str, flow_config: str) -> bool:
        """添加任务流程"""
        if not self.config.has_section('TaskFlow'):
            self.config.add_section('TaskFlow')
        
        self.config.set('TaskFlow', task_name, flow_config)
        return self.save_config()
        
    def add_task_payloads(self, task_name: str, payloads: List[Dict[str, Any]]) -> bool:
        """添加任务负载"""
        if not self.config.has_section('TaskPayloads'):
            self.config.add_section('TaskPayloads')
        
        # 删除现有的步骤定义
        keys_to_remove = [key for key in self.config['TaskPayloads'].keys() 
                         if key.startswith(f"{task_name}.")]
        for key in keys_to_remove:
            self.config.remove_option('TaskPayloads', key)
        
        # 添加新的步骤定义
        for i, payload in enumerate(payloads, 1):
            key = f"{task_name}.{i}"
            value = json.dumps(payload, ensure_ascii=False)
            self.config.set('TaskPayloads', key, value)
        
        return self.save_config()
        
    def remove_task(self, task_name: str) -> bool:
        """删除任务"""
        success = True
        
        # 从TaskFlow删除
        if self.config.has_section('TaskFlow') and self.config.has_option('TaskFlow', task_name):
            self.config.remove_option('TaskFlow', task_name)
        
        # 从TaskPayloads删除
        if self.config.has_section('TaskPayloads'):
            keys_to_remove = [key for key in self.config['TaskPayloads'].keys() 
                             if key.startswith(f"{task_name}.")]
            for key in keys_to_remove:
                self.config.remove_option('TaskPayloads', key)
        
        # 从TaskKeywords删除
        if self.config.has_section('TaskKeywords') and self.config.has_option('TaskKeywords', task_name):
            self.config.remove_option('TaskKeywords', task_name)
        
        return self.save_config()
        
    def migrate_from_old_config(self, old_config_file: str) -> bool:
        """从旧配置文件迁移"""
        try:
            old_config = configparser.ConfigParser()
            old_config.read(old_config_file, encoding='utf-8')
            
            # 迁移TaskSchedule到TaskFlow
            if old_config.has_section('TaskSchedule'):
                if not self.config.has_section('TaskFlow'):
                    self.config.add_section('TaskFlow')
                    
                for task_name, schedule_str in old_config['TaskSchedule'].items():
                    # 转换格式：添加默认的条件触发
                    new_flow = f"{schedule_str}|none"
                    self.config.set('TaskFlow', task_name, new_flow)
            
            # 迁移TaskDefinitions到TaskPayloads
            if old_config.has_section('TaskDefinitions'):
                if not self.config.has_section('TaskPayloads'):
                    self.config.add_section('TaskPayloads')
                    
                # 按任务分组
                task_steps = {}
                for key, value in old_config['TaskDefinitions'].items():
                    if '.' in key:
                        task_name, step_num = key.rsplit('.', 1)
                        if task_name not in task_steps:
                            task_steps[task_name] = {}
                        task_steps[task_name][int(step_num)] = value
                
                # 转换为新格式
                for task_name, steps_dict in task_steps.items():
                    for step_num in sorted(steps_dict.keys()):
                        old_step = steps_dict[step_num]
                        new_step = self._convert_old_step_format(old_step)
                        key = f"{task_name}.{step_num}"
                        value = json.dumps(new_step, ensure_ascii=False)
                        self.config.set('TaskPayloads', key, value)
            
            # 迁移其他配置节
            for section_name in ['TaskKeywords', 'WebhookTemplates', 'SystemSettings']:
                if old_config.has_section(section_name):
                    if not self.config.has_section(section_name):
                        self.config.add_section(section_name)
                    for key, value in old_config[section_name].items():
                        self.config.set(section_name, key, value)
            
            return self.save_config()
            
        except Exception as e:
            self.logger.error(f"配置迁移失败: {e}")
            return False
            
    def _convert_old_step_format(self, old_step: str) -> Dict[str, Any]:
        """转换旧的步骤格式到新格式"""
        parts = old_step.split(':')
        if len(parts) < 2:
            return {"type": "unknown", "params": [], "options": {}}
        
        step_type = parts[0]
        params = parts[1].split(',') if parts[1] else []
        options_str = parts[2] if len(parts) > 2 else ""
        
        # 解析选项
        options = {"log": True, "realtime_output": True}
        if options_str:
            for opt in options_str.split(','):
                if '=' in opt:
                    key, value = opt.split('=', 1)
                    if value.lower() == 'true':
                        options[key] = True
                    elif value.lower() == 'false':
                        options[key] = False
                    elif value.isdigit():
                        options[key] = int(value)
                    else:
                        options[key] = value
        
        # 转换步骤类型
        type_mapping = {
            'adb_wake': 'adb_wake',
            'resolution': 'resolution_check',
            'command': 'command',
            'wait': 'wait'
        }
        
        new_type = type_mapping.get(step_type, step_type)
        
        return {
            "type": new_type,
            "params": params,
            "options": options
        }