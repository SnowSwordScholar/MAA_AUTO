"""
任务调度器核心模块
处理任务调度、队列管理、资源控制等
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Dict, List, Set, Optional, Union, Tuple
from enum import Enum
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import random

from .config import TaskConfig, ResourceGroup, config_manager, AppConfig, TriggerConfig
from .executor import task_executor
from .notification import notification_service

logger = logging.getLogger(__name__)

class SchedulerMode(Enum):
    """调度器模式"""
    SCHEDULER = "scheduler"
    SINGLE_TASK = "single_task"

@dataclass
class TaskQueueItem:
    task: TaskConfig
    trigger_key: Optional[str] = None


class TaskQueue:
    """任务队列"""
    
    def __init__(self):
        self.queue: List[TaskQueueItem] = []
        self.lock = asyncio.Lock()
    
    async def put(self, task: TaskConfig, trigger_key: Optional[str] = None):
        async with self.lock:
            item = TaskQueueItem(task=task, trigger_key=trigger_key)
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
        self.job_trigger_lookup.clear()
        self.task_triggers.clear()
        self.retry_counters.clear()
        self.retry_notified.clear()
        if self.retry_tasks:
            for task in self.retry_tasks.values():
                task.cancel()
            await asyncio.gather(*self.retry_tasks.values(), return_exceptions=True)
            self.retry_tasks.clear()
        self.pending_window_tasks.clear()
        self.task_configs = {task.id: task for task in config.tasks}

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
        
        logger.info(f"已加载并调度 {len(self.scheduler.get_jobs())} 个启用的任务触发器")

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
            delay_seconds = min(delay_seconds, 1)

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

        await self.task_queue.put(task, trigger_key)

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
                task = task_item.task
                trigger_key = task_item.trigger_key

                if not await self.resource_manager.can_start_task(task):
                    logger.info(f"资源不足，任务 '{task.name}' 重新加入队列")
                    await asyncio.sleep(5) # 等待资源释放
                    await self.task_queue.put(task, trigger_key) # 放回队列
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
            asyncio.create_task(self._execute_and_handle_completion(TaskQueueItem(task=task)))
        except Exception as e:
            await self.resource_manager.release_resource(task)
            logger.error(f"创建任务执行协程失败: {e}")
            raise

    async def _execute_and_handle_completion(self, task_item: TaskQueueItem):
        task = task_item.task
        trigger_key = task_item.trigger_key
        trigger = self.task_triggers.get(trigger_key) if trigger_key else task.primary_trigger
        retry_key = self._make_retry_key(task.id, trigger_key)

        result = None
        retry_count = self.retry_counters.get(retry_key, 0)
        skip_pre_tasks = retry_count > 0 and not task.retry_policy.rerun_pre_tasks
        if skip_pre_tasks:
            logger.info(
                "任务 '%s' 第 %d 次尝试时跳过前置任务以加速重试",
                task.name,
                retry_count + 1
            )
        try:
            result = await self.executor.execute_task(task, skip_pre_tasks=skip_pre_tasks)
        except Exception as e:
            logger.error(f"执行任务 '{task.name}' 时发生错误: {e}", exc_info=True)
        finally:
            await self.resource_manager.release_resource(task)

        success = bool(result.success) if result else False
        if success:
            self.retry_counters.pop(retry_key, None)
            self.retry_notified.pop(retry_key, None)
            retry_task = self.retry_tasks.pop(retry_key, None)
            if retry_task:
                retry_task.cancel()
        else:
            await self._handle_retry(task, trigger_key, trigger, retry_key)

        await self._handle_post_execution(task, trigger_key, trigger, success)

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
        retry_task = asyncio.create_task(self._retry_after_delay(task, trigger_key, retry_key, delay))
        self.retry_tasks[retry_key] = retry_task
        logger.warning(f"任务 '{task.name}' 将在 {delay} 秒后进行第 {current} 次重试")

    async def _retry_after_delay(self, task: TaskConfig, trigger_key: Optional[str], retry_key: str, delay: int):
        try:
            await asyncio.sleep(delay)
            if not task.enabled:
                logger.info(f"任务 '{task.name}' 已禁用，取消后续重试")
                return

            if self.is_running and self.mode == SchedulerMode.SCHEDULER:
                await self.task_queue.put(task, trigger_key)
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

    async def _flush_pending_window_tasks(self):
        if not self.pending_window_tasks:
            return
        for task_id, trigger_key in self.pending_window_tasks:
            task = self.task_configs.get(task_id)
            if not task or not task.enabled:
                continue
            await self.task_queue.put(task, trigger_key)
        self.pending_window_tasks.clear()

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