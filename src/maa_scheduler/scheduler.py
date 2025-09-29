"""
任务调度器核心模块
处理任务调度、队列管理、资源控制等
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Callable
from enum import Enum
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
import random

from .config import TaskConfig, ResourceGroup, config_manager
from .executor import TaskExecutor, TaskStatus, task_executor
from .notification import notification_service

logger = logging.getLogger(__name__)

class SchedulerMode(Enum):
    """调度器模式"""
    SCHEDULER = "scheduler"    # 调度模式
    SINGLE_TASK = "single_task"  # 单任务模式

class TaskQueue:
    """任务队列"""
    
    def __init__(self):
        self.queue: List[TaskConfig] = []
        self.lock = asyncio.Lock()
    
    async def put(self, task: TaskConfig):
        """添加任务到队列"""
        async with self.lock:
            # 按优先级插入（优先级越低数字越大，越先执行）
            inserted = False
            for i, queued_task in enumerate(self.queue):
                if task.priority < queued_task.priority:
                    self.queue.insert(i, task)
                    inserted = True
                    break
            
            if not inserted:
                self.queue.append(task)
            
            logger.info(f"任务已加入队列: {task.name}, 队列长度: {len(self.queue)}")
    
    async def get(self) -> Optional[TaskConfig]:
        """从队列获取任务"""
        async with self.lock:
            if self.queue:
                task = self.queue.pop(0)
                logger.info(f"从队列获取任务: {task.name}, 剩余队列长度: {len(self.queue)}")
                return task
            return None
    
    async def remove(self, task_id: str) -> bool:
        """从队列移除任务"""
        async with self.lock:
            for i, task in enumerate(self.queue):
                if task.id == task_id:
                    removed_task = self.queue.pop(i)
                    logger.info(f"任务已从队列移除: {removed_task.name}")
                    return True
            return False
    
    def size(self) -> int:
        """获取队列大小"""
        return len(self.queue)
    
    def get_tasks(self) -> List[TaskConfig]:
        """获取队列中的所有任务"""
        return self.queue.copy()

class ResourceManager:
    """资源管理器"""
    
    def __init__(self):
        self.resource_groups: Dict[str, ResourceGroup] = {}
        self.running_tasks_by_group: Dict[str, Set[str]] = {}
        self.lock = asyncio.Lock()
    
    def load_resource_groups(self):
        """加载资源分组配置"""
        config = config_manager.load_app_config()
        for group in config.resource_groups:
            self.resource_groups[group.name] = group
            if group.name not in self.running_tasks_by_group:
                self.running_tasks_by_group[group.name] = set()
    
    async def can_start_task(self, task_config: TaskConfig) -> bool:
        """检查是否可以启动任务"""
        async with self.lock:
            group_name = task_config.resource_group
            
            if group_name not in self.resource_groups:
                logger.error(f"未知的资源分组: {group_name}")
                return False
            
            group = self.resource_groups[group_name]
            running_count = len(self.running_tasks_by_group[group_name])
            
            return running_count < group.max_concurrent
    
    async def allocate_resource(self, task_config: TaskConfig) -> bool:
        """分配资源"""
        async with self.lock:
            if await self.can_start_task(task_config):
                self.running_tasks_by_group[task_config.resource_group].add(task_config.id)
                logger.info(f"为任务分配资源: {task_config.name}, 分组: {task_config.resource_group}")
                return True
            return False
    
    async def release_resource(self, task_config: TaskConfig):
        """释放资源"""
        async with self.lock:
            group_name = task_config.resource_group
            if group_name in self.running_tasks_by_group:
                self.running_tasks_by_group[group_name].discard(task_config.id)
                logger.info(f"释放任务资源: {task_config.name}, 分组: {group_name}")
    
    def get_group_status(self, group_name: str) -> Dict:
        """获取资源分组状态"""
        if group_name not in self.resource_groups:
            return {}
        
        group = self.resource_groups[group_name]
        running_count = len(self.running_tasks_by_group.get(group_name, set()))
        
        return {
            'name': group.name,
            'description': group.description,
            'max_concurrent': group.max_concurrent,
            'running_count': running_count,
            'available': group.max_concurrent - running_count,
            'running_tasks': list(self.running_tasks_by_group.get(group_name, set()))
        }
    
    def get_all_groups_status(self) -> Dict[str, Dict]:
        """获取所有资源分组状态"""
        return {name: self.get_group_status(name) for name in self.resource_groups}

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.task_queue = TaskQueue()
        self.resource_manager = ResourceManager()
        self.mode = SchedulerMode.SCHEDULER
        self.executor = task_executor
        
        # 运行状态
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        
        # 任务配置缓存
        self.task_configs: Dict[str, TaskConfig] = {}
        
        # 回调函数
        self.on_task_completed: Optional[Callable] = None
    
    def set_mode(self, mode: SchedulerMode):
        """设置调度器模式"""
        old_mode = self.mode
        self.mode = mode
        
        logger.info(f"调度器模式变更: {old_mode.value} -> {mode.value}")
        
        if mode == SchedulerMode.SINGLE_TASK and old_mode == SchedulerMode.SCHEDULER:
            # 切换到单任务模式时，停止所有定时任务
            self._pause_all_scheduled_jobs()
        elif mode == SchedulerMode.SCHEDULER and old_mode == SchedulerMode.SINGLE_TASK:
            # 切换到调度模式时，恢复定时任务
            self._resume_all_scheduled_jobs()
    
    def _pause_all_scheduled_jobs(self):
        """暂停所有定时任务"""
        for job in self.scheduler.get_jobs():
            job.pause()
        logger.info("所有定时任务已暂停")
    
    def _resume_all_scheduled_jobs(self):
        """恢复所有定时任务"""
        for job in self.scheduler.get_jobs():
            job.resume()
        logger.info("所有定时任务已恢复")
    
    async def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("调度器已在运行中")
            return
        
        logger.info("启动任务调度器")
        
        # 加载资源分组
        self.resource_manager.load_resource_groups()
        
        # 加载任务配置
        await self.reload_tasks()
        
        # 启动 APScheduler
        self.scheduler.start()
        
        # 启动工作进程
        self.worker_task = asyncio.create_task(self._worker_loop())
        
        self.is_running = True
        
        # 发送启动通知
        await notification_service.notify_scheduler_status("已启动", "任务调度器已成功启动")
    
    async def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        logger.info("停止任务调度器")
        
        # 停止接受新任务
        self.is_running = False
        
        # 停止 APScheduler
        self.scheduler.shutdown()
        
        # 取消所有正在运行的任务
        running_tasks = self.executor.get_running_tasks()
        for task_id in running_tasks:
            await self.executor.cancel_task(task_id)
        
        # 停止工作进程
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        # 发送停止通知
        await notification_service.notify_scheduler_status("已停止", "任务调度器已停止")
    
    async def reload_tasks(self):
        """重新加载任务配置"""
        logger.info("重新加载任务配置")
        
        # 清除现有任务
        self.scheduler.remove_all_jobs()
        self.task_configs.clear()
        
        # 加载新的任务配置
        tasks = config_manager.load_tasks_config()
        
        for task in tasks:
            if not task.enabled:
                continue
            
            self.task_configs[task.id] = task
            
            # 添加到调度器
            try:
                await self._add_task_to_scheduler(task)
            except Exception as e:
                logger.error(f"添加任务到调度器失败: {task.name}, 错误: {e}")
        
        logger.info(f"已加载 {len(self.task_configs)} 个任务")
    
    async def _add_task_to_scheduler(self, task: TaskConfig):
        """添加任务到调度器"""
        trigger = self._create_trigger(task)
        
        if trigger:
            self.scheduler.add_job(
                func=self._schedule_task,
                trigger=trigger,
                args=[task.id],
                id=task.id,
                name=task.name,
                replace_existing=True
            )
            logger.info(f"任务已添加到调度器: {task.name}")
    
    def _create_trigger(self, task: TaskConfig):
        """创建触发器"""
        trigger_config = task.trigger
        
        if trigger_config.trigger_type == "cron":
            if not trigger_config.cron_expression:
                logger.error(f"Cron 触发器缺少表达式: {task.name}")
                return None
            
            try:
                return CronTrigger.from_crontab(trigger_config.cron_expression)
            except Exception as e:
                logger.error(f"无效的 Cron 表达式: {trigger_config.cron_expression}, 错误: {e}")
                return None
        
        elif trigger_config.trigger_type == "interval":
            if not trigger_config.interval_seconds:
                logger.error(f"间隔触发器缺少间隔时间: {task.name}")
                return None
            
            return IntervalTrigger(seconds=trigger_config.interval_seconds)
        
        elif trigger_config.trigger_type == "random":
            # 随机触发器需要特殊处理
            return self._create_random_trigger(task)
        
        else:
            logger.error(f"未知的触发器类型: {trigger_config.trigger_type}")
            return None
    
    def _create_random_trigger(self, task: TaskConfig):
        """创建随机触发器"""
        trigger_config = task.trigger
        
        if not trigger_config.random_start_time or not trigger_config.random_end_time:
            logger.error(f"随机触发器缺少时间范围: {task.name}")
            return None
        
        # 计算下一个随机时间
        next_run_time = self._calculate_random_time(
            trigger_config.random_start_time,
            trigger_config.random_end_time
        )
        
        if next_run_time:
            # 使用 DateTrigger 实现单次触发，然后在任务完成后重新调度
            return DateTrigger(run_date=next_run_time)
        
        return None
    
    def _calculate_random_time(self, start_time_str: str, end_time_str: str) -> Optional[datetime]:
        """计算随机时间"""
        try:
            now = datetime.now()
            today = now.date()
            
            # 解析时间
            start_hour, start_minute = map(int, start_time_str.split(':'))
            end_hour, end_minute = map(int, end_time_str.split(':'))
            
            start_time = datetime.combine(today, datetime.min.time().replace(hour=start_hour, minute=start_minute))
            end_time = datetime.combine(today, datetime.min.time().replace(hour=end_hour, minute=end_minute))
            
            # 如果结束时间早于开始时间，说明跨越了午夜
            if end_time <= start_time:
                end_time += timedelta(days=1)
            
            # 如果当前时间已经超过了今天的时间范围，计算明天的时间
            if now > end_time:
                start_time += timedelta(days=1)
                end_time += timedelta(days=1)
            elif now > start_time:
                start_time = now + timedelta(minutes=1)  # 至少1分钟后执行
            
            # 生成随机时间
            time_diff = end_time - start_time
            random_seconds = random.uniform(0, time_diff.total_seconds())
            random_time = start_time + timedelta(seconds=random_seconds)
            
            return random_time
        
        except Exception as e:
            logger.error(f"计算随机时间失败: {e}")
            return None
    
    async def _schedule_task(self, task_id: str):
        """调度任务执行"""
        if not self.is_running or self.mode != SchedulerMode.SCHEDULER:
            return
        
        if task_id not in self.task_configs:
            logger.error(f"任务配置不存在: {task_id}")
            return
        
        task = self.task_configs[task_id]
        
        # 检查任务是否已在运行
        if task_id in self.executor.running_tasks:
            logger.warning(f"任务已在运行中，跳过: {task.name}")
            return
        
        # 添加到队列
        await self.task_queue.put(task)
        
        # 如果是随机触发器，重新调度下一次执行
        if task.trigger.trigger_type == "random":
            await self._reschedule_random_task(task)
    
    async def _reschedule_random_task(self, task: TaskConfig):
        """重新调度随机任务"""
        try:
            # 计算下一个随机时间
            next_run_time = self._calculate_random_time(
                task.trigger.random_start_time,
                task.trigger.random_end_time
            )
            
            if next_run_time:
                # 更新任务的下次执行时间
                self.scheduler.modify_job(
                    job_id=task.id,
                    next_run_time=next_run_time
                )
                logger.info(f"随机任务已重新调度: {task.name}, 下次执行: {next_run_time}")
        
        except Exception as e:
            logger.error(f"重新调度随机任务失败: {task.name}, 错误: {e}")
    
    async def _worker_loop(self):
        """工作进程循环"""
        logger.info("工作进程已启动")
        
        try:
            while self.is_running:
                # 获取队列中的任务
                task = await self.task_queue.get()
                
                if task is None:
                    # 队列为空，等待一段时间
                    await asyncio.sleep(1)
                    continue
                
                # 检查资源是否可用
                if not await self.resource_manager.can_start_task(task):
                    logger.info(f"资源不足，任务重新加入队列: {task.name}")
                    await self.task_queue.put(task)
                    await asyncio.sleep(5)  # 等待资源释放
                    continue
                
                # 分配资源并启动任务
                if await self.resource_manager.allocate_resource(task):
                    try:
                        await self.executor.start_task_async(task)
                        
                        # 创建任务完成监听器
                        asyncio.create_task(self._monitor_task_completion(task))
                        
                    except Exception as e:
                        logger.error(f"启动任务失败: {task.name}, 错误: {e}")
                        await self.resource_manager.release_resource(task)
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"工作进程异常: {e}", exc_info=True)
        
        logger.info("工作进程已停止")
    
    async def _monitor_task_completion(self, task: TaskConfig):
        """监控任务完成"""
        try:
            # 等待任务完成
            if task.id in self.executor.running_tasks:
                await self.executor.running_tasks[task.id]
            
            # 释放资源
            await self.resource_manager.release_resource(task)
            
            # 调用完成回调
            if self.on_task_completed:
                try:
                    await self.on_task_completed(task.id)
                except Exception as e:
                    logger.error(f"任务完成回调异常: {e}")
        
        except Exception as e:
            logger.error(f"监控任务完成异常: {e}", exc_info=True)
    
    async def execute_single_task(self, task_id: str) -> str:
        """执行单个任务（单任务模式）"""
        if self.mode != SchedulerMode.SINGLE_TASK:
            raise ValueError("当前不在单任务模式")
        
        if task_id not in self.task_configs:
            raise ValueError(f"任务不存在: {task_id}")
        
        task = self.task_configs[task_id]
        
        # 检查资源
        if not await self.resource_manager.can_start_task(task):
            raise ValueError(f"资源不足，无法启动任务: {task.name}")
        
        # 分配资源并启动任务
        if await self.resource_manager.allocate_resource(task):
            try:
                task_execution_id = await self.executor.start_task_async(task)
                
                # 创建任务完成监听器
                asyncio.create_task(self._monitor_task_completion(task))
                
                return task_execution_id
            
            except Exception as e:
                await self.resource_manager.release_resource(task)
                raise e
        else:
            raise ValueError(f"分配资源失败: {task.name}")
    
    def get_scheduler_status(self) -> Dict:
        """获取调度器状态"""
        return {
            'is_running': self.is_running,
            'mode': self.mode.value,
            'task_count': len(self.task_configs),
            'queue_size': self.task_queue.size(),
            'running_tasks': self.executor.get_running_tasks(),
            'resource_groups': self.resource_manager.get_all_groups_status(),
            'scheduled_jobs': len(self.scheduler.get_jobs()) if self.is_running else 0
        }
    
    def get_task_list(self) -> List[Dict]:
        """获取任务列表"""
        result = []
        for task in self.task_configs.values():
            status = self.executor.get_task_status(task.id)
            
            # 获取下次执行时间
            next_run_time = None
            try:
                job = self.scheduler.get_job(task.id)
                if job:
                    next_run_time = job.next_run_time
            except:
                pass
            
            result.append({
                'id': task.id,
                'name': task.name,
                'description': task.description,
                'enabled': task.enabled,
                'priority': task.priority,
                'resource_group': task.resource_group,
                'trigger_type': task.trigger.trigger_type,
                'status': status.value,
                'next_run_time': next_run_time.isoformat() if next_run_time else None
            })
        
        return result

# 全局调度器实例
scheduler = TaskScheduler()