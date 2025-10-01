"""
任务调度器核心模块
处理任务调度、队列管理、资源控制等
"""

import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Set, Optional, Union
from enum import Enum
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import random

from .config import TaskConfig, ResourceGroup, config_manager, AppConfig
from .executor import task_executor
from .notification import notification_service

logger = logging.getLogger(__name__)

class SchedulerMode(Enum):
    """调度器模式"""
    SCHEDULER = "scheduler"
    SINGLE_TASK = "single_task"

class TaskQueue:
    """任务队列"""
    
    def __init__(self):
        self.queue: List[TaskConfig] = []
        self.lock = asyncio.Lock()
    
    async def put(self, task: TaskConfig):
        async with self.lock:
            # 按优先级插入（数字越小优先级越高）
            for i, queued_task in enumerate(self.queue):
                if task.priority < queued_task.priority:
                    self.queue.insert(i, task)
                    logger.info(f"任务 '{task.name}' 已按优先级插入队列，当前队列长度: {len(self.queue)}")
                    return
            self.queue.append(task)
            logger.info(f"任务 '{task.name}' 已添加到队列末尾，当前队列长度: {len(self.queue)}")
    
    async def get(self) -> Optional[TaskConfig]:
        async with self.lock:
            if self.queue:
                task = self.queue.pop(0)
                logger.info(f"从队列获取任务: {task.name}, 剩余队列长度: {len(self.queue)}")
                return task
            return None
    
    def size(self) -> int:
        return len(self.queue)

    async def clear(self):
        async with self.lock:
            self.queue.clear()
            logger.info("任务队列已清空")

class ResourceManager:
    """资源管理器"""
    
    def __init__(self):
        self.resource_groups: Dict[str, ResourceGroup] = {}
        self.running_tasks_by_group: Dict[str, Set[str]] = {}
        self.lock = asyncio.Lock()
    
    def load_resource_groups(self, config: AppConfig):
        self.resource_groups.clear()
        self.running_tasks_by_group.clear()
        for group in config.resource_groups:
            self.resource_groups[group.name] = group
            self.running_tasks_by_group[group.name] = set()
        # 添加默认资源组
        if "default" not in self.resource_groups:
            default_group = ResourceGroup(name="default", description="默认资源组", max_concurrent=1)
            self.resource_groups["default"] = default_group
            self.running_tasks_by_group["default"] = set()
            
        logger.info(f"已加载 {len(self.resource_groups)} 个资源组")

    async def can_start_task(self, task_config: TaskConfig) -> bool:
        async with self.lock:
            group_name = task_config.resource_group
            if group_name not in self.resource_groups:
                logger.warning(f"任务 '{task_config.name}' 的资源组 '{group_name}' 不存在，将允许执行")
                return True
            
            group = self.resource_groups[group_name]
            running_count = len(self.running_tasks_by_group[group_name])
            return running_count < group.max_concurrent
    
    async def allocate_resource(self, task_config: TaskConfig):
        async with self.lock:
            group_name = task_config.resource_group
            if group_name in self.running_tasks_by_group:
                self.running_tasks_by_group[group_name].add(task_config.id)
                logger.info(f"为任务 '{task_config.name}' 分配资源 (组: {group_name})")
    
    async def release_resource(self, task_config: TaskConfig):
        async with self.lock:
            group_name = task_config.resource_group
            if group_name in self.running_tasks_by_group:
                self.running_tasks_by_group[group_name].discard(task_config.id)
                logger.info(f"释放任务 '{task_config.name}' 的资源 (组: {group_name})")

    def get_all_groups_status(self) -> Dict[str, Dict]:
        status = {}
        for name, group in self.resource_groups.items():
            running_count = len(self.running_tasks_by_group.get(name, set()))
            status[name] = {
                'name': group.name,
                'description': group.description,
                'max_concurrent': group.max_concurrent,
                'running_count': running_count,
                'available': group.max_concurrent - running_count,
                'running_tasks': list(self.running_tasks_by_group.get(name, []))
            }
        return status

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.task_queue = TaskQueue()
        self.resource_manager = ResourceManager()
        self.mode = SchedulerMode.SCHEDULER
        self.executor = task_executor
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        self.task_configs: Dict[str, TaskConfig] = {}

    async def start(self):
        if self.is_running:
            logger.warning("调度器已在运行中")
            return
        
        logger.info("启动任务调度器")
        await self.reload_tasks()
        if self.mode != SchedulerMode.SCHEDULER:
            logger.info("启动调度器时自动切换到自动调度模式")
            self.mode = SchedulerMode.SCHEDULER
        self.scheduler.start()
        self.worker_task = asyncio.create_task(self._worker_loop())
        self.is_running = True
        logger.info("任务调度器已成功启动")

    async def stop(self):
        if not self.is_running:
            return
        
        logger.info("正在停止任务调度器")
        self.is_running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        
        running_task_ids = self.executor.get_running_tasks()
        if running_task_ids:
            logger.info(f"正在取消 {len(running_task_ids)} 个正在运行的任务...")
            await asyncio.gather(*(self.executor.cancel_task(task_id) for task_id in running_task_ids))

        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("任务调度器已停止")

    async def reload_tasks(self):
        logger.info("正在重新加载任务配置...")
        config = config_manager.get_config()
        self.resource_manager.load_resource_groups(config)
        
        self.scheduler.remove_all_jobs()
        self.task_configs = {task.id: task for task in config.tasks}
        
        for task_id, task in self.task_configs.items():
            if task.enabled:
                self._schedule_initial_task(task)
        
        logger.info(f"已加载并调度 {len(self.scheduler.get_jobs())} 个启用的任务")

    def _schedule_initial_task(self, task: TaskConfig):
        """为任务安排首次执行"""
        trigger = None
        run_date = None
        
        ttype = task.trigger.trigger_type
        if ttype == "scheduled":
            try:
                hour, minute = map(int, task.trigger.start_time.split(':'))
                trigger = CronTrigger(hour=hour, minute=minute, second=0)
            except (ValueError, AttributeError) as e:
                logger.error(f"任务 '{task.name}' 的定时触发器格式无效: {e}")
                return
        elif ttype == "interval":
            # 立即执行或在很短的延迟后执行，以便启动循环
            run_date = datetime.now() + timedelta(seconds=1)
        elif ttype == "random_time":
            run_date = self._calculate_next_random_time(task)
            if not run_date:
                return
        
        if trigger:
            self.scheduler.add_job(
                self._add_task_to_queue,
                trigger,
                args=[task.id],
                id=task.id,
                name=task.name,
                replace_existing=True
            )
        elif run_date:
            self.scheduler.add_job(
                self._add_task_to_queue,
                DateTrigger(run_date=run_date),
                args=[task.id],
                id=task.id,
                name=task.name,
                replace_existing=True
            )
        logger.info(f"已为任务 '{task.name}' ({ttype}) 创建调度")

    async def _on_task_completed(self, task: TaskConfig):
        """任务完成后重新调度"""
        logger.debug(f"任务 '{task.name}' 完成，检查是否需要重新调度。")
        if not task.enabled or not self.is_running:
            return

        next_run_time = None
        ttype = task.trigger.trigger_type

        if ttype == "interval":
            interval = task.trigger.interval_minutes or 0
            next_run_time = datetime.now() + timedelta(minutes=interval)
            logger.info(f"任务 '{task.name}' (间隔) 将在 {next_run_time.strftime('%Y-%m-%d %H:%M:%S')} 再次运行")
        elif ttype == "random_time":
            next_run_time = self._calculate_next_random_time(task)
            if next_run_time:
                logger.info(f"任务 '{task.name}' (随机) 已重新调度在 {next_run_time.strftime('%Y-%m-%d %H:%M:%S')} 运行")

        if next_run_time:
            self.scheduler.add_job(
                self._add_task_to_queue,
                DateTrigger(run_date=next_run_time),
                args=[task.id],
                id=task.id,
                name=task.name,
                replace_existing=True
            )

    def _calculate_next_random_time(self, task: TaskConfig) -> Optional[datetime]:
        """计算下一个随机执行时间"""
        try:
            start_str = task.trigger.random_start_time
            end_str = task.trigger.random_end_time
            start_t = time.fromisoformat(start_str)
            end_t = time.fromisoformat(end_str)
            
            today = datetime.now().date()
            start_dt = datetime.combine(today, start_t)
            end_dt = datetime.combine(today, end_t)

            if end_dt <= start_dt: # 跨天
                end_dt += timedelta(days=1)

            now = datetime.now()
            if now > end_dt: # 如果今天的时间段已过，则计算明天的
                start_dt += timedelta(days=1)
                end_dt += timedelta(days=1)
            
            # 确保开始时间在未来
            effective_start_dt = max(now, start_dt)

            if effective_start_dt >= end_dt:
                # 如果当前时间已经晚于或等于结束时间，则计算明天的
                start_dt += timedelta(days=1)
                end_dt += timedelta(days=1)
                effective_start_dt = start_dt

            time_diff_seconds = (end_dt - effective_start_dt).total_seconds()
            random_seconds = random.uniform(0, time_diff_seconds)
            return effective_start_dt + timedelta(seconds=random_seconds)
        except (ValueError, AttributeError) as e:
            logger.error(f"计算任务 '{task.name}' 的随机时间失败: {e}")
            return None

    async def _add_task_to_queue(self, task_id: str):
        if not self.is_running:
            return
        if self.mode != SchedulerMode.SCHEDULER:
            logger.debug("当前为单任务模式，跳过自动调度任务: %s", task_id)
            return
        
        task = self.task_configs.get(task_id)
        if not task:
            logger.error(f"尝试调度一个不存在的任务ID: {task_id}")
            return
        
        if not task.enabled:
            logger.info(f"任务 '{task.name}' 已被禁用，跳过调度。")
            return

        if task.id in self.executor.get_running_tasks():
            logger.warning(f"任务 '{task.name}' 已在运行中，本次调度跳过。")
            return
        
        await self.task_queue.put(task)

    async def _worker_loop(self):
        logger.info("工作进程已启动")
        try:
            while self.is_running:
                if self.mode != SchedulerMode.SCHEDULER:
                    await asyncio.sleep(1)
                    continue
                task = await self.task_queue.get()
                if not task:
                    await asyncio.sleep(1)
                    continue
                
                if not await self.resource_manager.can_start_task(task):
                    logger.info(f"资源不足，任务 '{task.name}' 重新加入队列")
                    await asyncio.sleep(5) # 等待资源释放
                    await self.task_queue.put(task) # 放回队列
                    continue
                
                await self.resource_manager.allocate_resource(task)
                asyncio.create_task(self._execute_and_handle_completion(task))
        except asyncio.CancelledError:
            logger.info("工作进程被取消")
        except Exception as e:
            logger.error(f"工作进程异常: {e}", exc_info=True)
        logger.info("工作进程已停止")

    async def run_task_once(self, task: TaskConfig):
        """在当前模式下立即执行一个任务，遵循资源组约束"""
        if task is None:
            raise ValueError("任务配置不存在，无法执行")

        if self.is_running and self.mode != SchedulerMode.SINGLE_TASK:
            raise RuntimeError("调度器正在运行，请先停止调度器或切换到单任务模式")

        # 确保资源分组信息已加载
        if not self.resource_manager.resource_groups:
            self.resource_manager.load_resource_groups(config_manager.get_config())

        if task.id in self.executor.get_running_tasks():
            raise RuntimeError("任务已在执行中")

        if not await self.resource_manager.can_start_task(task):
            raise RuntimeError("所属资源组正在忙，请稍后再试")

        # 缓存任务配置供状态查询使用
        self.task_configs[task.id] = task

        try:
            await self.resource_manager.allocate_resource(task)
        except Exception as e:
            logger.error(f"分配任务资源失败: {e}")
            raise RuntimeError("资源分配失败，请检查资源组配置") from e

        logger.info(f"手动执行任务: {task.name} (ID: {task.id})")

        try:
            asyncio.create_task(self._execute_and_handle_completion(task))
        except Exception as e:
            await self.resource_manager.release_resource(task)
            logger.error(f"创建任务执行协程失败: {e}")
            raise

    async def _execute_and_handle_completion(self, task: TaskConfig):
        try:
            await self.executor.execute_task(task)
        except Exception as e:
            logger.error(f"执行任务 '{task.name}' 时发生错误: {e}", exc_info=True)
        finally:
            await self.resource_manager.release_resource(task)
            # 任务完成后，触发重新调度逻辑
            await self._on_task_completed(task)

    async def set_mode(self, mode: Union[SchedulerMode, str]):
        if isinstance(mode, str):
            try:
                mode = SchedulerMode(mode)
            except ValueError as exc:
                raise ValueError(f"不支持的调度模式: {mode}") from exc

        if self.mode == mode:
            return

        self.mode = mode
        if mode == SchedulerMode.SINGLE_TASK:
            await self.task_queue.clear()
            logger.info("调度器已切换到单任务模式，自动调度暂停")
        else:
            logger.info("调度器已切换到自动调度模式")

    def get_scheduler_status(self) -> Dict:
        return {
            'is_running': self.is_running,
            'mode': self.mode.value,
            'task_count': len(self.task_configs),
            'queue_size': self.task_queue.size(),
            'running_tasks': self.executor.get_running_tasks(),
            'resource_groups': self.resource_manager.get_all_groups_status(),
            'scheduled_jobs': len(self.scheduler.get_jobs()) if self.scheduler.running else 0
        }
    
    def get_task_list(self) -> List[Dict]:
        result = []
        for task in self.task_configs.values():
            status = self.executor.get_task_status(task.id)
            job = self.scheduler.get_job(task.id)
            next_run_time = job.next_run_time if job else None
            
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