"""
任务调度器核心模块
处理任务调度、队列管理、资源控制等
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from typing import Dict, List, Set, Optional, Union, Tuple, Any
from enum import Enum
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import random

from .config import TaskConfig, ResourceGroup, config_manager, AppConfig, TriggerConfig
from .executor import task_executor
from .notification import notification_service
from .events import event_bus

logger = logging.getLogger(__name__)

class SchedulerMode(Enum):
    """调度器模式"""
    SCHEDULER = "scheduler"
    SINGLE_TASK = "single_task"

@dataclass
class TaskQueueItem:
    task: TaskConfig
    trigger_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskQueue:
    """任务队列"""
    
    def __init__(self):
        self.queue: List[TaskQueueItem] = []
        self.lock = asyncio.Lock()
    
    async def put(
        self,
        task: TaskConfig,
        trigger_key: Optional[str] = None,
        *,
        metadata: Optional[Dict[str, Any]] = None
    ):
        async with self.lock:
            item = TaskQueueItem(task=task, trigger_key=trigger_key, metadata=metadata or {})
            # 按优先级插入（数字越小优先级越高）
            for i, queued_task in enumerate(self.queue):
                if task.priority < queued_task.task.priority:
                    self.queue.insert(i, item)
                    logger.info(f"任务 '{task.name}' 已按优先级插入队列，当前队列长度: {len(self.queue)}")
                    return
            self.queue.append(item)
            logger.info(f"任务 '{task.name}' 已添加到队列末尾，当前队列长度: {len(self.queue)}")
    
    async def get(self) -> Optional[TaskQueueItem]:
        async with self.lock:
            if self.queue:
                item = self.queue.pop(0)
                logger.info(f"从队列获取任务: {item.task.name}, 剩余队列长度: {len(self.queue)}")
                return item
            return None

    async def remove_task(self, task_id: str) -> int:
        async with self.lock:
            original_length = len(self.queue)
            if original_length == 0:
                return 0
            self.queue = [item for item in self.queue if item.task.id != task_id]
            removed = original_length - len(self.queue)
            if removed:
                logger.info(f"已从队列移除任务 '{task_id}' 的 {removed} 个待执行项，当前队列长度: {len(self.queue)}")
            return removed

    async def retain_tasks(self, valid_ids: Set[str]) -> int:
        async with self.lock:
            original_length = len(self.queue)
            if original_length == 0:
                return 0
            self.queue = [item for item in self.queue if item.task.id in valid_ids]
            removed = original_length - len(self.queue)
            if removed:
                logger.info(f"清理队列中无效任务 {removed} 个，当前队列长度: {len(self.queue)}")
            return removed
    
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
        try:
            self.mode = SchedulerMode(config_manager.get_config().app.mode)
        except Exception:
            self.mode = SchedulerMode.SCHEDULER
        self.executor = task_executor
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        self.task_configs: Dict[str, TaskConfig] = {}
        self.task_triggers: Dict[str, TriggerConfig] = {}
        self.job_trigger_lookup: Dict[str, str] = {}
        self.retry_counters: Dict[str, int] = {}
        self.retry_notified: Dict[str, bool] = {}
        self.retry_tasks: Dict[str, asyncio.Task] = {}
        self.pending_window_tasks: List[Tuple[str, Optional[str]]] = []
        self.trigger_last_run: Dict[str, datetime] = {}
        self.active_trigger_keys: Dict[str, Optional[str]] = {}
        self.preempted_tasks: Set[str] = set()
        self.success_retry_tasks: Dict[str, asyncio.Task] = {}
        self.success_retry_counters: Dict[str, int] = {}

    async def _notify_scheduler_state(self):
        status = self.get_scheduler_status()
        status["timestamp"] = datetime.now().isoformat()
        await event_bus.publish({
            "type": "scheduler_status",
            "data": status
        })

    async def _notify_task_list(self):
        await event_bus.publish({
            "type": "task_list",
            "data": self.get_task_list(),
            "timestamp": datetime.now().isoformat()
        })

    async def start(self):
        if self.is_running:
            logger.warning("调度器已在运行中")
            return
        
        logger.info("启动任务调度器")
        try:
            self.mode = SchedulerMode(config_manager.get_config().app.mode)
        except Exception:
            logger.warning("配置中的调度模式无效，回退到自动调度模式")
            self.mode = SchedulerMode.SCHEDULER
        await self.reload_tasks()
        self.scheduler.start()
        self.is_running = True
        await self._flush_pending_window_tasks()
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info(f"任务调度器已成功启动 (当前模式: {self.mode.value})")
        await self._notify_scheduler_state()
        await self._notify_task_list()

    async def stop(self):
        if not self.is_running:
            return

        logger.info("正在停止任务调度器")
        self.is_running = False
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

        await self._cancel_all_running_tasks(reason="stop")

        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        await self._cancel_retry_handles()
        logger.info("任务调度器已停止")
        await self._notify_scheduler_state()
        await self._notify_task_list()

    async def _purge_task(self, task_id: str):
        await self.task_queue.remove_task(task_id)

        self.pending_window_tasks = [item for item in self.pending_window_tasks if item[0] != task_id]
        self.preempted_tasks.discard(task_id)
        self.active_trigger_keys.pop(task_id, None)

        prefix = f"{task_id}:"

        def _purge_dict(store: Dict[str, Any]):
            removed = False
            for key in list(store.keys()):
                if key.startswith(prefix):
                    store.pop(key, None)
                    removed = True
            if removed:
                logger.debug(f"清理任务 '{task_id}' 相关的状态: {store.__class__.__name__}")

        _purge_dict(self.retry_counters)
        _purge_dict(self.retry_notified)
        _purge_dict(self.success_retry_counters)

        for key in list(self.retry_tasks.keys()):
            if key.startswith(prefix):
                handle = self.retry_tasks.pop(key)
                handle.cancel()

        for key in list(self.success_retry_tasks.keys()):
            if key.startswith(prefix):
                handle = self.success_retry_tasks.pop(key)
                handle.cancel()

        for key in list(self.trigger_last_run.keys()):
            if key.startswith(prefix):
                self.trigger_last_run.pop(key, None)

        self.job_trigger_lookup = {
            job_id: trigger_key
            for job_id, trigger_key in self.job_trigger_lookup.items()
            if not trigger_key or not trigger_key.startswith(prefix)
        }

    async def reload_tasks(self):
        logger.info("正在重新加载任务配置...")
        config = config_manager.get_config()
        self.resource_manager.load_resource_groups(config)
        
        self.scheduler.remove_all_jobs()
        self.job_trigger_lookup.clear()
        self.task_triggers.clear()
        self.retry_counters.clear()
        self.retry_notified.clear()
        self.success_retry_counters.clear()
        await self._cancel_retry_handles()
        self.pending_window_tasks.clear()
        self.task_configs = {task.id: task for task in config.tasks}

        valid_task_ids = set(self.task_configs.keys())
        await self.task_queue.retain_tasks(valid_task_ids)

        for task_id, task in self.task_configs.items():
            if not task.enabled:
                await self.cancel_task(task_id, reason="disabled")

        for task in self.task_configs.values():
            if not task.enabled:
                continue

            triggers = task.triggers or ([task.trigger] if task.trigger else [])
            if not triggers:
                logger.warning(f"任务 '{task.name}' 未配置触发器，已跳过")
                continue

            for index, trigger in enumerate(triggers):
                trigger_key = f"{task.id}:{index}"
                self.task_triggers[trigger_key] = trigger
                self._schedule_trigger(task, trigger_key, trigger)
        valid_trigger_keys = set(self.task_triggers.keys())
        if self.trigger_last_run:
            self.trigger_last_run = {
                key: value for key, value in self.trigger_last_run.items()
                if key in valid_trigger_keys
            }
        logger.info(f"已加载并调度 {len(self.scheduler.get_jobs())} 个启用的任务触发器")
        await self._notify_scheduler_state()
        await self._notify_task_list()

    def _schedule_trigger(self, task: TaskConfig, trigger_key: str, trigger: TriggerConfig):
        """根据触发器配置创建调度任务"""
        job_id_prefix = trigger_key

        def register_job(job_id: str):
            self.job_trigger_lookup[job_id] = trigger_key

        ttype = trigger.trigger_type
        logger.debug(f"为任务 '{task.name}' 注册触发器 {ttype} (key={trigger_key})")

        if ttype == "scheduled":
            try:
                hour, minute = self._parse_time(trigger.start_time)
                cron = CronTrigger(hour=hour, minute=minute, second=0)
                job_id = f"{job_id_prefix}:daily"
                self.scheduler.add_job(
                    self._add_task_to_queue,
                    cron,
                    args=[task.id, trigger_key],
                    id=job_id,
                    name=f"{task.name}-daily",
                    replace_existing=True
                )
                register_job(job_id)
                if self._is_time_window_active(trigger.start_time, trigger.end_time):
                    if self.is_running:
                        asyncio.create_task(self._add_task_to_queue(task.id, trigger_key))
                    else:
                        self.pending_window_tasks.append((task.id, trigger_key))
            except ValueError as e:
                logger.error(f"任务 '{task.name}' 的定时触发器格式无效: {e}")
        elif ttype == "interval":
            self._schedule_interval_run(task, trigger_key, trigger, initial=True)
        elif ttype == "random_time":
            run_time = self._calculate_next_random_time(trigger, task.name)
            if not run_time:
                logger.warning(f"任务 '{task.name}' 随机触发器未能计算到下一次执行时间")
                return
            job_id = f"{job_id_prefix}:random"
            self.scheduler.add_job(
                self._add_task_to_queue,
                DateTrigger(run_date=run_time),
                args=[task.id, trigger_key],
                id=job_id,
                name=f"{task.name}-random",
                replace_existing=True
            )
            register_job(job_id)
            logger.info(f"已为任务 '{task.name}' 注册随机触发，下一次在 {run_time}")
        elif ttype == "weekly":
            if not trigger.days_of_week:
                logger.error(f"任务 '{task.name}' 周期触发缺少星期配置")
                return
            hour, minute = self._parse_time(trigger.start_time)
            cron = CronTrigger(day_of_week=','.join(str(d) for d in trigger.days_of_week), hour=hour, minute=minute, second=0)
            job_id = f"{job_id_prefix}:weekly"
            self.scheduler.add_job(
                self._add_task_to_queue,
                cron,
                args=[task.id, trigger_key],
                id=job_id,
                name=f"{task.name}-weekly",
                replace_existing=True
            )
            register_job(job_id)
        elif ttype == "monthly":
            if not trigger.days_of_month:
                logger.error(f"任务 '{task.name}' 月度触发缺少日期配置")
                return
            hour, minute = self._parse_time(trigger.start_time)
            cron = CronTrigger(day=','.join(str(d) for d in trigger.days_of_month), hour=hour, minute=minute, second=0)
            job_id = f"{job_id_prefix}:monthly"
            self.scheduler.add_job(
                self._add_task_to_queue,
                cron,
                args=[task.id, trigger_key],
                id=job_id,
                name=f"{task.name}-monthly",
                replace_existing=True
            )
            register_job(job_id)
        elif ttype == "specific_date":
            if not trigger.specific_datetimes:
                logger.error(f"任务 '{task.name}' 特定日期触发缺少日期配置")
                return
            for idx, dt_str in enumerate(trigger.specific_datetimes):
                try:
                    run_time = self._parse_datetime(dt_str)
                except ValueError:
                    logger.error(f"任务 '{task.name}' 特定日期 '{dt_str}' 格式无效，应为 YYYY-MM-DD HH:MM")
                    continue
                job_id = f"{job_id_prefix}:date:{idx}"
                self.scheduler.add_job(
                    self._add_task_to_queue,
                    DateTrigger(run_date=run_time),
                    args=[task.id, trigger_key],
                    id=job_id,
                    name=f"{task.name}-date-{idx}",
                    replace_existing=True
                )
                register_job(job_id)
        else:
            logger.error(f"任务 '{task.name}' 包含未知的触发类型: {ttype}")

    def _schedule_interval_run(
        self,
        task: TaskConfig,
        trigger_key: str,
        trigger: TriggerConfig,
        initial: bool = False,
        delay_seconds: Optional[int] = None
    ):
        interval_minutes = trigger.interval_minutes or 0
        if interval_minutes <= 0 and delay_seconds is None:
            logger.warning(f"任务 '{task.name}' 的间隔触发未配置 interval_minutes，将默认等待60秒")
            interval_minutes = 1

        if delay_seconds is None:
            delay_seconds = max(interval_minutes * 60, 1)

        if initial:
            last_run = self.trigger_last_run.get(trigger_key)
            if last_run:
                elapsed = max((datetime.now() - last_run).total_seconds(), 0.0)
                if elapsed < delay_seconds:
                    delay_seconds = max(delay_seconds - elapsed, 1.0)
                else:
                    delay_seconds = 1.0
            else:
                delay_seconds = min(delay_seconds, 1.0)

        run_time = datetime.now() + timedelta(seconds=delay_seconds)
        job_id = f"{trigger_key}:interval"
        self.scheduler.add_job(
            self._add_task_to_queue,
            DateTrigger(run_date=run_time),
            args=[task.id, trigger_key],
            id=job_id,
            name=f"{task.name}-interval",
            replace_existing=True
        )
        self.job_trigger_lookup[job_id] = trigger_key
        logger.info(f"任务 '{task.name}' 间隔触发将在 {run_time.strftime('%Y-%m-%d %H:%M:%S')} 执行 (delay={delay_seconds}s)")

    @staticmethod
    def _parse_time(time_value: Optional[str]) -> Tuple[int, int]:
        if not time_value:
            return 0, 0
        try:
            hour, minute = map(int, time_value.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
            return hour, minute
        except (ValueError, AttributeError):
            raise ValueError(f"时间格式无效: {time_value}")

    @staticmethod
    def _parse_datetime(datetime_value: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                normalized = datetime_value.replace('T', ' ')
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(datetime_value)
        except ValueError as exc:
            raise ValueError(f"日期时间格式无效: {datetime_value}") from exc

    def _calculate_next_random_time(self, trigger: TriggerConfig, task_name: Optional[str] = None) -> Optional[datetime]:
        """计算下一个随机执行时间"""
        try:
            start_str = trigger.random_start_time or trigger.start_time
            end_str = trigger.random_end_time or trigger.end_time
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
            if task_name:
                logger.error(f"计算任务 '{task_name}' 的随机时间失败: {e}")
            else:
                logger.error(f"计算随机时间失败: {e}")
            return None

    async def _add_task_to_queue(self, task_id: str, trigger_key: Optional[str] = None):
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
        trigger = self.task_triggers.get(trigger_key) if trigger_key else task.primary_trigger

        if trigger and trigger.trigger_type == "interval":
            await self._preempt_lower_priority_tasks(task)

        # 对于间隔/随机触发，立即排定下一次执行
        if trigger and trigger_key:
            if trigger.trigger_type == "interval":
                self._schedule_interval_run(task, trigger_key, trigger, initial=False)
            elif trigger.trigger_type == "random_time":
                next_run = self._calculate_next_random_time(trigger, task.name)
                if next_run:
                    job_id = f"{trigger_key}:random"
                    self.scheduler.add_job(
                        self._add_task_to_queue,
                        DateTrigger(run_date=next_run),
                        args=[task.id, trigger_key],
                        id=job_id,
                        name=f"{task.name}-random",
                        replace_existing=True
                    )
                    self.job_trigger_lookup[job_id] = trigger_key
                    logger.info(f"任务 '{task.name}' 下一次随机触发时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

        queue_metadata: Dict[str, Any] = {}
        if trigger:
            queue_metadata['trigger_type'] = trigger.trigger_type
        if trigger_key:
            queue_metadata['trigger_key'] = trigger_key
        queue_metadata.setdefault('origin', 'scheduler')
        await self.task_queue.put(task, trigger_key, metadata=queue_metadata)

    async def _worker_loop(self):
        logger.info("工作进程已启动")
        try:
            while self.is_running:
                if self.mode != SchedulerMode.SCHEDULER:
                    await asyncio.sleep(1)
                    continue
                task_item = await self.task_queue.get()
                if not task_item:
                    await asyncio.sleep(1)
                    continue
                task = self.task_configs.get(task_item.task.id, task_item.task)
                task_item.task = task
                trigger_key = task_item.trigger_key

                if not task.enabled:
                    logger.info(f"任务 '{task.name}' 已被禁用，跳过队列中的待执行项")
                    continue

                if not await self.resource_manager.can_start_task(task):
                    logger.info(f"资源不足，任务 '{task.name}' 重新加入队列")
                    await asyncio.sleep(5)
                    await self.task_queue.put(task, trigger_key, metadata=task_item.metadata)
                    continue

                await self.resource_manager.allocate_resource(task)
                asyncio.create_task(self._execute_and_handle_completion(task_item))
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
            meta: Dict[str, Any] = {'manual': True, 'trigger_type': 'manual'}
            asyncio.create_task(self._execute_and_handle_completion(TaskQueueItem(task=task, metadata=meta)))
        except Exception as e:
            await self.resource_manager.release_resource(task)
            logger.error(f"创建任务执行协程失败: {e}")
            raise

    async def cancel_task(self, task_id: str, *, reason: str = "manual", purge_queue: bool = True) -> bool:
        cancelled = False
        if task_id in self.executor.get_running_tasks():
            cancelled = await self.executor.cancel_task(task_id, reason=reason)
        if purge_queue:
            await self._purge_task(task_id)
        await self._notify_scheduler_state()
        return cancelled

    async def _execute_and_handle_completion(self, task_item: TaskQueueItem):
        task = task_item.task
        trigger_key = task_item.trigger_key
        trigger = self.task_triggers.get(trigger_key) if trigger_key else task.primary_trigger
        retry_key = self._make_retry_key(task.id, trigger_key)

        metadata: Dict[str, Any] = dict(task_item.metadata or {})
        if trigger_key and 'trigger_key' not in metadata:
            metadata['trigger_key'] = trigger_key
        if trigger and 'trigger_type' not in metadata:
            metadata['trigger_type'] = trigger.trigger_type

        result = None
        retry_count = self.retry_counters.get(retry_key, 0)
        skip_pre_tasks = retry_count > 0 and not task.retry_policy.rerun_pre_tasks
        if skip_pre_tasks:
            logger.info(
                "任务 '%s' 第 %d 次尝试时跳过前置任务以加速重试",
                task.name,
                retry_count + 1
            )
        if retry_count > 0:
            metadata.setdefault('retry', True)
            metadata.setdefault('retry_attempt', retry_count)
            metadata.setdefault('origin', 'retry')
        metadata.setdefault('origin', 'manual' if metadata.get('manual') else 'scheduler')
        self.active_trigger_keys[task.id] = trigger_key
        preempted = False
        try:
            try:
                result = await self.executor.execute_task(
                    task,
                    skip_pre_tasks=skip_pre_tasks,
                    metadata=metadata
                )
            except Exception as e:
                logger.error(f"执行任务 '{task.name}' 时发生错误: {e}", exc_info=True)
            finally:
                await self.resource_manager.release_resource(task)

            if task.id in self.preempted_tasks:
                preempted = True
                self.preempted_tasks.discard(task.id)
                if result:
                    result.message = "任务被高优先级任务抢占，等待窗口恢复"

            if trigger_key and not preempted:
                timestamp = result.end_time if result and result.end_time else datetime.now()
                self.trigger_last_run[trigger_key] = timestamp

            success = bool(result.success) if result else False
            cancelled = bool(result and result.message == "任务被取消") and not preempted

            if success:
                self.retry_counters.pop(retry_key, None)
                self.retry_notified.pop(retry_key, None)
                retry_task = self.retry_tasks.pop(retry_key, None)
                if retry_task:
                    retry_task.cancel()
                await self._handle_success_retry(task, trigger_key, trigger, retry_key)
            elif cancelled:
                logger.info(f"任务 '{task.name}' 被取消，本轮不触发重试")
            elif not preempted:
                await self._handle_retry(task, trigger_key, trigger, retry_key)

            await self._handle_post_execution(task, trigger_key, trigger, success)
        finally:
            self.active_trigger_keys.pop(task.id, None)

    def _make_retry_key(self, task_id: str, trigger_key: Optional[str]) -> str:
        return f"{task_id}:{trigger_key or 'manual'}"

    async def _handle_retry(
        self,
        task: TaskConfig,
        trigger_key: Optional[str],
        trigger: Optional[TriggerConfig],
        retry_key: str
    ):
        policy = task.retry_policy
        if not policy.enabled:
            self.retry_counters.pop(retry_key, None)
            self.retry_notified.pop(retry_key, None)
            return

        max_retries = policy.max_retries
        if max_retries <= 0:
            return

        current = self.retry_counters.get(retry_key, 0) + 1
        self.retry_counters[retry_key] = current

        if policy.notify_after_retries and current >= policy.notify_after_retries and not self.retry_notified.get(retry_key):
            title = f"任务重试提醒: {task.name}"
            content = (
                f"任务 '{task.name}' 连续失败 {current} 次，正在进行自动重试。\n"
                f"触发器: {trigger.trigger_type if trigger else 'unknown'}\n"
                f"最大重试次数: {max_retries}"
            )
            await notification_service.send_webhook_notification(title, content, "task-retry")
            self.retry_notified[retry_key] = True

        if current > max_retries:
            logger.error(f"任务 '{task.name}' 达到最大重试次数 {max_retries}，停止自动重试。")
            self.retry_counters.pop(retry_key, None)
            return

        delay = max(policy.delay_seconds, 1)
        if retry_key in self.retry_tasks:
            self.retry_tasks[retry_key].cancel()
        retry_task = asyncio.create_task(self._retry_after_delay(task, trigger_key, retry_key, delay, current))
        self.retry_tasks[retry_key] = retry_task
        logger.warning(f"任务 '{task.name}' 将在 {delay} 秒后进行第 {current} 次重试")

    async def _retry_after_delay(
        self,
        task: TaskConfig,
        trigger_key: Optional[str],
        retry_key: str,
        delay: int,
        attempt: int
    ):
        try:
            await asyncio.sleep(delay)
            if not task.enabled:
                logger.info(f"任务 '{task.name}' 已禁用，取消后续重试")
                return

            if self.is_running and self.mode == SchedulerMode.SCHEDULER:
                trigger = self.task_triggers.get(trigger_key) if trigger_key else None
                metadata: Dict[str, Any] = {
                    'retry': True,
                    'retry_attempt': attempt,
                    'origin': 'retry',
                }
                if trigger_key:
                    metadata['trigger_key'] = trigger_key
                if trigger:
                    metadata['trigger_type'] = trigger.trigger_type
                await self.task_queue.put(task, trigger_key, metadata=metadata)
            else:
                logger.info(f"调度器当前未处于自动模式，对任务 '{task.name}' 进行手动重试")
                try:
                    await self.run_task_once(task)
                except Exception as exc:
                    logger.error(f"手动重试任务 '{task.name}' 失败: {exc}", exc_info=True)
        except asyncio.CancelledError:
            logger.debug(f"任务 '{task.name}' 的重试计划已取消")
            raise
        finally:
            self.retry_tasks.pop(retry_key, None)

    async def _handle_success_retry(
        self,
        task: TaskConfig,
        trigger_key: Optional[str],
        trigger: Optional[TriggerConfig],
        retry_key: str
    ):
        policy = task.retry_policy
        if not policy.enabled or not policy.retry_on_success_within_window:
            self.success_retry_counters.pop(retry_key, None)
            pending = self.success_retry_tasks.pop(retry_key, None)
            if pending:
                pending.cancel()
            return

        if not trigger_key:
            logger.debug("任务 '%s' 成功执行，但未提供触发器键，跳过成功重试", task.name)
            self.success_retry_counters.pop(retry_key, None)
            pending = self.success_retry_tasks.pop(retry_key, None)
            if pending:
                pending.cancel()
            return

        if not trigger or trigger.trigger_type != "scheduled":
            logger.debug("任务 '%s' 成功，但触发器非定时类型，跳过成功重试", task.name)
            self.success_retry_counters.pop(retry_key, None)
            pending = self.success_retry_tasks.pop(retry_key, None)
            if pending:
                pending.cancel()
            return

        if not self._is_time_window_active(trigger.start_time, trigger.end_time):
            self.success_retry_counters.pop(retry_key, None)
            pending = self.success_retry_tasks.pop(retry_key, None)
            if pending:
                pending.cancel()
            return

        current = self.success_retry_counters.get(retry_key, 0)
        limit = policy.success_retry_max
        if limit is not None and current >= limit:
            logger.info(
                "任务 '%s' 已达到成功重试上限 %d，本轮不再继续在窗口内触发",
                task.name,
                limit
            )
            self.success_retry_counters.pop(retry_key, None)
            pending = self.success_retry_tasks.pop(retry_key, None)
            if pending:
                pending.cancel()
            return

        delay = policy.success_retry_delay_seconds
        if delay is None or delay <= 0:
            delay = max(policy.delay_seconds or 1, 1)

        if retry_key in self.success_retry_tasks:
            existing = self.success_retry_tasks.pop(retry_key)
            existing.cancel()

        handle = asyncio.create_task(
            self._success_retry_after_delay(task, trigger_key, retry_key, delay, trigger, current)
        )
        self.success_retry_tasks[retry_key] = handle
        logger.info(
            "任务 '%s' 在时间窗口内成功完成，将在 %d 秒后尝试再次执行 (成功重试计数: %d)",
            task.name,
            delay,
            current + 1
        )

    async def _success_retry_after_delay(
        self,
        task: TaskConfig,
        trigger_key: Optional[str],
        retry_key: str,
        delay: int,
        trigger: TriggerConfig,
        previous_count: int
    ):
        try:
            await asyncio.sleep(delay)

            policy = task.retry_policy
            if not policy.enabled or not policy.retry_on_success_within_window:
                self.success_retry_counters.pop(retry_key, None)
                return

            if not self.is_running or self.mode != SchedulerMode.SCHEDULER:
                logger.debug("调度器非自动模式，跳过任务 '%s' 的成功重试", task.name)
                return

            if not task.enabled:
                logger.info("任务 '%s' 已禁用，跳过成功重试", task.name)
                self.success_retry_counters.pop(retry_key, None)
                return

            if not self._is_time_window_active(trigger.start_time, trigger.end_time):
                logger.info("任务 '%s' 的时间窗口已结束，停止成功重试", task.name)
                self.success_retry_counters.pop(retry_key, None)
                return

            limit = policy.success_retry_max
            current = self.success_retry_counters.get(retry_key, previous_count)
            if limit is not None and current >= limit:
                logger.info(
                    "任务 '%s' 达到成功重试上限 %d，停止额外执行",
                    task.name,
                    limit
                )
                self.success_retry_counters.pop(retry_key, None)
                return

            next_attempt = current + 1
            metadata: Dict[str, Any] = {
                'success_retry': True,
                'success_retry_attempt': next_attempt,
                'origin': 'success_retry',
            }
            if trigger_key:
                metadata['trigger_key'] = trigger_key
            if trigger:
                metadata['trigger_type'] = trigger.trigger_type
            await self.task_queue.put(task, trigger_key, metadata=metadata)
            self.success_retry_counters[retry_key] = next_attempt
            logger.info("任务 '%s' 成功重试已重新加入执行队列", task.name)
        except asyncio.CancelledError:
            logger.debug("任务 '%s' 的成功重试计划已取消", task.name)
            raise
        finally:
            self.success_retry_tasks.pop(retry_key, None)

    async def _preempt_lower_priority_tasks(self, incoming_task: TaskConfig):
        if not self.is_running:
            return

        running_ids = self.executor.get_running_tasks()
        if not running_ids:
            return

        for running_id in running_ids:
            if running_id == incoming_task.id:
                continue

            running_trigger_key = self.active_trigger_keys.get(running_id)
            if not running_trigger_key:
                continue

            running_task = self.task_configs.get(running_id)
            if not running_task:
                continue

            if running_task.resource_group != incoming_task.resource_group:
                continue

            if running_task.priority <= incoming_task.priority:
                continue

            running_trigger = self.task_triggers.get(running_trigger_key)
            if not running_trigger or running_trigger.trigger_type != "scheduled":
                continue

            if not self._is_time_window_active(running_trigger.start_time, running_trigger.end_time):
                continue

            logger.info(
                "高优先级任务 '%s' 正在抢占资源，取消时间段任务 '%s'",
                incoming_task.name,
                running_task.name
            )
            self.preempted_tasks.add(running_id)
            if not await self.executor.cancel_task(running_id, reason="preempt"):
                self.preempted_tasks.discard(running_id)
                logger.warning("无法取消正在运行的任务 '%s'，继续执行", running_task.name)
                continue

            pair = (running_task.id, running_trigger_key)
            if pair not in self.pending_window_tasks:
                self.pending_window_tasks.append(pair)

    async def _flush_pending_window_tasks(self):
        if not self.pending_window_tasks:
            return
        for task_id, trigger_key in self.pending_window_tasks:
            task = self.task_configs.get(task_id)
            if not task or not task.enabled:
                continue
            await self.task_queue.put(task, trigger_key)
        self.pending_window_tasks.clear()

    async def _cancel_all_running_tasks(self, *, reason: str = "manual"):
        running_task_ids = self.executor.get_running_tasks()
        if not running_task_ids:
            return
        logger.info(
            "正在取消 %d 个正在运行的任务 (原因: %s)...",
            len(running_task_ids),
            reason
        )
        await asyncio.gather(
            *(self.cancel_task(task_id, reason=reason, purge_queue=False) for task_id in running_task_ids)
        )

    @staticmethod
    def _is_time_window_active(start_time: Optional[str], end_time: Optional[str]) -> bool:
        if not start_time:
            return False
        try:
            start = time.fromisoformat(start_time)
        except ValueError:
            return False

        now = datetime.now().time()

        if not end_time:
            return now.hour == start.hour and now.minute == start.minute

        try:
            end = time.fromisoformat(end_time)
        except ValueError:
            return False

        if start == end:
            return True

        if start < end:
            return start <= now <= end

        return now >= start or now <= end

    async def _handle_post_execution(
        self,
        task: TaskConfig,
        trigger_key: Optional[str],
        trigger: Optional[TriggerConfig],
        success: bool
    ):
        if not self.is_running or not task.enabled:
            return

        if trigger_key and trigger:
            if trigger.trigger_type == "interval":
                logger.debug(f"任务 '{task.name}' 间隔触发本轮执行{'成功' if success else '失败'}")
            elif trigger.trigger_type == "random_time":
                logger.debug(f"任务 '{task.name}' 随机触发本轮执行{'成功' if success else '失败'}")

        if trigger and trigger.trigger_type == "interval" and self.pending_window_tasks:
            await self._flush_pending_window_tasks()

    async def set_mode(self, mode: Union[SchedulerMode, str]):
        if isinstance(mode, str):
            try:
                mode = SchedulerMode(mode)
            except ValueError as exc:
                raise ValueError(f"不支持的调度模式: {mode}") from exc

        if self.mode == mode:
            return

        self.mode = mode
        # 持久化模式到配置文件
        config = config_manager.get_config()
        config.app.mode = self.mode.value
        config_manager.save_config(config)

        if mode == SchedulerMode.SINGLE_TASK:
            await self.task_queue.clear()
            await self._cancel_all_running_tasks(reason="mode-switch")
            await self._cancel_retry_handles()
            logger.info("调度器已切换到单任务模式，自动调度暂停并终止所有正在执行的任务")
        else:
            logger.info("调度器已切换到自动调度模式")
        await self._notify_scheduler_state()
        await self._notify_task_list()

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

    async def _cancel_retry_handles(self):
        pending: List[asyncio.Task] = []
        if self.retry_tasks:
            pending.extend(self.retry_tasks.values())
        if self.success_retry_tasks:
            pending.extend(self.success_retry_tasks.values())

        if not pending:
            return

        for task in pending:
            task.cancel()

        await asyncio.gather(*pending, return_exceptions=True)
        self.retry_tasks.clear()
        self.success_retry_tasks.clear()
    
    def get_task_list(self) -> List[Dict]:
        result = []
        for task in self.task_configs.values():
            status = self.executor.get_task_status(task.id)
            next_run_time = self.get_task_next_run_time(task.id)
            
            primary_trigger = task.primary_trigger
            result.append({
                'id': task.id,
                'name': task.name,
                'description': task.description,
                'enabled': task.enabled,
                'priority': task.priority,
                'resource_group': task.resource_group,
                'trigger_type': primary_trigger.trigger_type if primary_trigger else None,
                'status': status.value,
                'next_run_time': next_run_time.isoformat() if next_run_time else None
            })
        return result

    def get_task_next_run_time(self, task_id: str) -> Optional[datetime]:
        relevant_jobs = [
            job for job in self.scheduler.get_jobs()
            if job.id and job.id.startswith(f"{task_id}:")
        ]

        if not relevant_jobs:
            return None

        next_times = [job.next_run_time for job in relevant_jobs if getattr(job, "next_run_time", None)]
        if not next_times:
            return None
        return min(next_times)

# 全局调度器实例
scheduler = TaskScheduler()