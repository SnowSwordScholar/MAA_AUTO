"""
任务调度器核心引擎
"""

import threading
import time
import queue
import logging
import signal
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .config import ConfigManager
from .executors import ADBExecutor, CommandExecutor, HttpExecutor, FileExecutor

class TaskType(Enum):
    """任务类型枚举"""
    INTERVAL = "interval"      # 间隔执行
    TIMEWINDOW = "timewindow"  # 时间窗口
    TRIGGER = "trigger"        # 条件触发

@dataclass
class TaskSchedule:
    """任务调度配置"""
    name: str
    task_type: TaskType
    time_params: str
    priority: int
    random_range: Tuple[int, int]
    queue_group: str
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None

@dataclass
class TaskDefinition:
    """任务定义"""
    name: str
    steps: List[Dict[str, Any]]
    keywords: Dict[str, Dict[str, Any]]

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.running = False
        self.config = ConfigManager(config_file)
        
        # 任务队列和状态
        self.task_queues = {}
        self.active_tasks = {}
        self.schedules = {}
        self.definitions = {}
        
        # 执行器
        self.executors = {
            'adb': ADBExecutor(self.config),
            'command': CommandExecutor(self.config),
            'http': HttpExecutor(self.config),
            'file': FileExecutor(self.config)
        }
        
        # 设置日志
        self.setup_logging()
        
        # 加载配置
        self.load_configuration()
        
        # 初始化任务队列
        self.init_task_queues()
        
        # 信号处理
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def setup_logging(self):
        """设置日志"""
        from pathlib import Path
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        
        log_level = getattr(logging, self.config.get_system_setting('log_level', 'INFO').upper())
        log_file = log_dir / "maa_scheduler.log"
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("MAA任务调度器启动")
        
    def load_configuration(self):
        """加载配置"""
        try:
            # 加载任务调度配置
            schedule_configs = self.config.get_task_schedules()
            for task_name, config in schedule_configs.items():
                schedule = TaskSchedule(
                    name=task_name,
                    task_type=TaskType(config['type']),
                    time_params=config['time_params'],
                    priority=config['priority'],
                    random_range=self._parse_random_range(config['random_range']),
                    queue_group=config['queue_group']
                )
                self.schedules[task_name] = schedule
            
            # 加载任务定义
            definition_configs = self.config.get_task_definitions()
            keyword_configs = self.config.get_task_keywords()
            
            for task_name, steps in definition_configs.items():
                definition = TaskDefinition(
                    name=task_name,
                    steps=steps,
                    keywords=keyword_configs.get(task_name, {})
                )
                self.definitions[task_name] = definition
            
            self.logger.info(f"加载了 {len(self.schedules)} 个任务调度和 {len(self.definitions)} 个任务定义")
            
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            raise
            
    def _parse_random_range(self, range_str: str) -> Tuple[int, int]:
        """解析随机范围"""
        try:
            if '-' in range_str:
                min_val, max_val = map(int, range_str.split('-'))
                return (min_val, max_val)
            else:
                val = int(range_str)
                return (val, val)
        except ValueError:
            return (0, 0)
            
    def init_task_queues(self):
        """初始化任务队列"""
        queue_groups = set(schedule.queue_group for schedule in self.schedules.values())
        for group in queue_groups:
            self.task_queues[group] = queue.PriorityQueue()
            
    def calculate_next_execution(self, schedule: TaskSchedule) -> Optional[datetime]:
        """计算下次执行时间"""
        now = datetime.now()
        
        if schedule.task_type == TaskType.INTERVAL:
            # 间隔执行
            if schedule.last_execution is None:
                return now
            
            # 解析间隔时间
            interval_str = schedule.time_params.lower()
            if interval_str.endswith('h'):
                hours = float(interval_str[:-1])
                interval = timedelta(hours=hours)
            elif interval_str.endswith('m'):
                minutes = float(interval_str[:-1])
                interval = timedelta(minutes=minutes)
            elif interval_str.endswith('s'):
                seconds = float(interval_str[:-1])
                interval = timedelta(seconds=seconds)
            else:
                hours = float(interval_str)
                interval = timedelta(hours=hours)
            
            return schedule.last_execution + interval
            
        elif schedule.task_type == TaskType.TIMEWINDOW:
            # 时间窗口执行
            start_hour, end_hour = map(float, schedule.time_params.split('-'))
            
            # 处理跨日情况
            if start_hour > end_hour:
                # 跨日执行 (如 5-4 表示 5点到次日4点)
                current_hour = now.hour + now.minute/60
                if current_hour >= start_hour or current_hour < end_hour:
                    # 在执行窗口内，检查是否今天已执行
                    if schedule.last_execution and schedule.last_execution.date() == now.date():
                        # 今天已执行，计算明天的执行时间
                        next_start = (now + timedelta(days=1)).replace(
                            hour=int(start_hour), 
                            minute=int((start_hour % 1) * 60), 
                            second=0, 
                            microsecond=0
                        )
                        return next_start
                    else:
                        return now  # 今天未执行，可以执行
                else:
                    # 不在执行窗口内，计算下一个执行窗口开始时间
                    if current_hour < start_hour:
                        next_start = now.replace(
                            hour=int(start_hour), 
                            minute=int((start_hour % 1) * 60), 
                            second=0, 
                            microsecond=0
                        )
                    else:
                        next_start = (now + timedelta(days=1)).replace(
                            hour=int(start_hour), 
                            minute=int((start_hour % 1) * 60), 
                            second=0, 
                            microsecond=0
                        )
                    return next_start
            else:
                # 同日执行
                current_hour = now.hour + now.minute/60
                if start_hour <= current_hour <= end_hour:
                    # 在执行窗口内，检查是否今天已执行
                    if schedule.last_execution and schedule.last_execution.date() == now.date():
                        # 今天已执行，计算明天的执行时间
                        next_start = (now + timedelta(days=1)).replace(
                            hour=int(start_hour), 
                            minute=int((start_hour % 1) * 60), 
                            second=0, 
                            microsecond=0
                        )
                        return next_start
                    else:
                        return now  # 今天未执行，可以执行
                else:
                    # 计算下一个执行窗口
                    if current_hour < start_hour:
                        next_start = now.replace(
                            hour=int(start_hour), 
                            minute=int((start_hour % 1) * 60), 
                            second=0, 
                            microsecond=0
                        )
                    else:
                        next_start = (now + timedelta(days=1)).replace(
                            hour=int(start_hour), 
                            minute=int((start_hour % 1) * 60), 
                            second=0, 
                            microsecond=0
                        )
                    return next_start
                        
        return None
        
    def should_execute_task(self, schedule: TaskSchedule) -> bool:
        """判断任务是否应该执行"""
        now = datetime.now()
        
        # 检查任务是否已在执行
        if schedule.name in self.active_tasks:
            return False
        
        # 检查执行时间
        next_time = self.calculate_next_execution(schedule)
        if next_time is None or now < next_time:
            return False
        
        return True
        
    def get_executor_for_step(self, step_type: str):
        """根据步骤类型获取执行器"""
        for executor in self.executors.values():
            if step_type in executor.get_supported_steps():
                return executor
        return None
        
    def execute_task_step(self, step: Dict[str, Any], task_name: str) -> Tuple[bool, str]:
        """执行任务步骤"""
        step_type = step['type']
        params = step['params']
        options = step.get('options', {})
        
        # 为步骤添加任务名称（用于日志和关键词检测）
        options['task_name'] = task_name
        
        executor = self.get_executor_for_step(step_type)
        if executor is None:
            return False, f"未找到步骤类型 '{step_type}' 的执行器"
        
        try:
            return executor.execute_step(step_type, params, options)
        except Exception as e:
            error_msg = f"执行步骤失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def check_keywords_in_output(self, output: str, task_name: str):
        """检查输出中的关键词"""
        if task_name not in self.definitions:
            return
        
        definition = self.definitions[task_name]
        
        for keyword_type, keyword_config in definition.keywords.items():
            keywords = keyword_config['keywords']
            action = keyword_config['action']
            
            for keyword in keywords:
                if keyword in output:
                    self.logger.info(f"任务 {task_name} 检测到关键词 '{keyword}' (类型: {keyword_type})")
                    
                    # 如果action是webhook相关，发送通知
                    if action.startswith('webhook=') and action != 'webhook=none':
                        webhook_template = action.split('=', 1)[1]
                        self.send_webhook_notification(webhook_template, task_name, output)
                    
                    break
                    
    def send_webhook_notification(self, template_name: str, task_name: str, content: str = ""):
        """发送WebHook通知"""
        try:
            # 使用HTTP执行器发送WebHook
            http_executor = self.executors['http']
            success, result = http_executor.execute_step('webhook', [template_name, content], {})
            
            if success:
                self.logger.info(f"WebHook通知发送成功: {template_name}")
            else:
                self.logger.error(f"WebHook通知发送失败: {result}")
                
        except Exception as e:
            self.logger.error(f"发送WebHook通知异常: {e}")
            
    def execute_task(self, task_name: str):
        """执行任务"""
        if task_name not in self.definitions:
            self.logger.error(f"未找到任务定义: {task_name}")
            return
        
        definition = self.definitions[task_name]
        schedule = self.schedules.get(task_name)
        
        self.logger.info(f"开始执行任务: {task_name}")
        self.active_tasks[task_name] = datetime.now()
        
        all_output = []
        
        try:
            for i, step in enumerate(definition.steps, 1):
                self.logger.info(f"执行步骤 {i}/{len(definition.steps)}: {step['type']}")
                
                success, result = self.execute_task_step(step, task_name)
                
                if step.get('options', {}).get('log', True):
                    if success:
                        self.logger.info(f"步骤 {i} 成功: {result}")
                    else:
                        self.logger.error(f"步骤 {i} 失败: {result}")
                
                # 收集输出用于关键词检测
                all_output.append(result)
                
                if not success:
                    self.logger.error(f"任务 {task_name} 在步骤 {i} 失败")
                    break
            else:
                self.logger.info(f"任务 {task_name} 执行完成")
                
            # 检查关键词
            full_output = '\n'.join(all_output)
            self.check_keywords_in_output(full_output, task_name)
                
            # 更新最后执行时间
            if schedule:
                schedule.last_execution = datetime.now()
                
        except Exception as e:
            self.logger.error(f"任务 {task_name} 执行异常: {e}")
        finally:
            # 从活跃任务中移除
            if task_name in self.active_tasks:
                del self.active_tasks[task_name]
                
    def signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"收到信号 {signum}，准备停止")
        self.running = False
        
    def add_task(self, task_name: str, schedule_config: str, step_definitions: List[str]) -> bool:
        """动态添加任务"""
        try:
            # 添加到配置
            success = self.config.add_task_schedule(task_name, schedule_config)
            if success:
                success = self.config.add_task_definition(task_name, step_definitions)
            
            if success:
                # 重新加载配置
                self.load_configuration()
                self.logger.info(f"动态添加任务成功: {task_name}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"动态添加任务失败: {e}")
            return False
            
    def remove_task(self, task_name: str) -> bool:
        """动态删除任务"""
        try:
            success = self.config.remove_task(task_name)
            
            if success:
                # 从内存中删除
                if task_name in self.schedules:
                    del self.schedules[task_name]
                if task_name in self.definitions:
                    del self.definitions[task_name]
                if task_name in self.active_tasks:
                    del self.active_tasks[task_name]
                    
                self.logger.info(f"动态删除任务成功: {task_name}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"动态删除任务失败: {e}")
            return False
            
    def get_task_status(self) -> Dict[str, Any]:
        """获取任务状态"""
        return {
            'total_tasks': len(self.schedules),
            'active_tasks': len(self.active_tasks),
            'task_list': list(self.schedules.keys()),
            'active_task_list': list(self.active_tasks.keys()),
            'queue_groups': list(self.task_queues.keys())
        }
        
    def main_loop(self):
        """主循环"""
        self.running = True
        self.logger.info("任务调度器开始运行")
        
        while self.running:
            try:
                # 检查所有任务调度
                for task_name, schedule in self.schedules.items():
                    if self.should_execute_task(schedule):
                        # 添加随机延迟
                        delay = random.randint(*schedule.random_range)
                        if delay > 0:
                            self.logger.info(f"任务 {task_name} 随机延迟 {delay} 秒")
                            time.sleep(delay)
                        
                        # 在新线程中执行任务
                        task_thread = threading.Thread(
                            target=self.execute_task,
                            args=(task_name,),
                            name=f"Task-{task_name}"
                        )
                        task_thread.daemon = True
                        task_thread.start()
                
                # 休眠一段时间再检查
                time.sleep(60)  # 每分钟检查一次
                
            except Exception as e:
                self.logger.error(f"主循环异常: {e}")
                time.sleep(60)
        
        self.logger.info("任务调度器停止")

def main():
    """主函数"""
    scheduler = TaskScheduler()
    try:
        scheduler.main_loop()
    except KeyboardInterrupt:
        scheduler.logger.info("接收到中断信号，正在停止...")
    except Exception as e:
        scheduler.logger.error(f"调度器异常: {e}")
    finally:
        scheduler.running = False

if __name__ == "__main__":
    main()