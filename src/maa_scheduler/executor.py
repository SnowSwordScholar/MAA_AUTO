"""
任务执行器模块
处理任务的执行、前置后置处理、日志管理等
"""

import asyncio
import logging
import shlex
from collections import deque
from pathlib import Path
from typing import Dict, Optional, Tuple, Deque, Any, List, Set
from datetime import datetime
from enum import Enum

from .config import TaskConfig, config_manager
from .notification import notification_service

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskResult:
    """任务执行结果"""
    def __init__(self, task_id: str, success: bool, message: str = "", 
                 return_code: int = 0, stdout: str = "", stderr: str = ""):
        self.task_id = task_id
        self.success = success
        self.message = message
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.duration: Optional[float] = None

class TaskExecutor:
    """任务执行器"""
    
    def __init__(self):
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self.temp_log_files: Dict[str, Path] = {}
        self.live_logs: Dict[str, Deque[str]] = {}
        self.task_history: Deque[Dict[str, Any]] = deque(maxlen=50)
        try:
            self.last_known_resolution: Optional[str] = config_manager.get_config().app.last_device_resolution
        except Exception:
            self.last_known_resolution = None
        self.connected_devices: Set[str] = set()
    
    async def execute_task(self, task_config: TaskConfig, *, skip_pre_tasks: bool = False) -> TaskResult:
        """执行任务的完整流程"""
        logger.info(f"开始执行任务: {task_config.name} (ID: {task_config.id})")

        result = TaskResult(task_config.id, False)
        result.start_time = datetime.now()

        current_task = asyncio.current_task()
        if current_task is not None:
            self.running_tasks[task_config.id] = current_task

        self.live_logs[task_config.id] = deque(maxlen=500)

        try:
            if skip_pre_tasks:
                logger.info(f"任务 '{task_config.name}' 在本次尝试中跳过前置任务执行")
            else:
                pre_task_success = await self._execute_pre_tasks(task_config)
                if not pre_task_success:
                    raise Exception("前置任务执行失败")

            success, return_code, stdout, stderr = await self._execute_main_task(task_config)

            result.success = success
            result.return_code = return_code
            result.stdout = stdout
            result.stderr = stderr
            result.message = "任务执行成功" if success else f"任务执行失败，返回码: {return_code}"

            if success:
                logger.info(f"任务 '{task_config.name}' 执行成功")
            else:
                logger.error(f"任务 '{task_config.name}' 执行失败, 返回码: {return_code}\nStderr: {stderr}")

            await self._execute_post_tasks(task_config, result)

        except asyncio.CancelledError:
            result.success = False
            result.message = "任务被取消"
            logger.warning(f"任务 '{task_config.name}' 已被取消")
            await notification_service.notify_task_status(task_config, "任务被取消")
        except Exception as e:
            result.success = False
            result.message = f"任务执行异常: {e}"
            logger.error(f"任务 '{task_config.name}' 执行异常: {e}", exc_info=True)
            await notification_service.notify_system_error(
                f"任务 '{task_config.name}' 异常",
                str(e),
                category="task-error"
            )
        finally:
            result.end_time = datetime.now()
            if result.start_time:
                result.duration = (result.end_time - result.start_time).total_seconds()

            self.task_results[task_config.id] = result

            status = (
                TaskStatus.COMPLETED.value if result.success
                else (TaskStatus.CANCELLED.value if result.message == "任务被取消" else TaskStatus.FAILED.value)
            )
            history_entry = {
                "task_id": task_config.id,
                "task_name": task_config.name,
                "status": status,
                "success": result.success,
                "message": result.message,
                "resource_group": task_config.resource_group,
                "start_time": result.start_time.isoformat() if result.start_time else None,
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "duration": result.duration,
                "return_code": result.return_code,
            }
            self.task_history.append(history_entry)

            if task_config.id in self.running_tasks:
                self.running_tasks.pop(task_config.id)

        return result

    async def _execute_pre_tasks(self, task_config: TaskConfig) -> bool:
        """执行前置任务，如分辨率调整和ADB唤醒"""
        device_id = task_config.adb_device_id
        if device_id:
            connected = await self._ensure_adb_connection(device_id, task_config.id)
            if not connected:
                return False

        if task_config.enable_resolution_switch and task_config.target_resolution:
            resolution_ok = await self._ensure_target_resolution(task_config)
            if not resolution_ok:
                return False

        if not task_config.enable_adb_wakeup:
            return True

        if not device_id:
            logger.warning(f"任务 '{task_config.name}' 启用了ADB唤醒但未配置设备ID，跳过操作。")
            return True

        logger.info(f"为任务 '{task_config.name}' 执行ADB唤醒，设备: {device_id}")
        try:
            # 唤醒设备
            await self._run_adb_command(device_id, "input keyevent KEYCODE_WAKEUP", task_config.id)
            await asyncio.sleep(0.5)
            # 解锁屏幕（上划）
            await self._run_adb_command(device_id, "input swipe 300 1000 300 500", task_config.id)
            logger.info(f"ADB唤醒/解锁命令已发送至 {device_id}")

            delay = task_config.adb_launch_delay_seconds or 0
            if delay > 0:
                logger.info(f"等待 {delay} 秒后执行应用启动命令")
                await asyncio.sleep(delay)

            if task_config.adb_launch_package:
                pkg = task_config.adb_launch_package
                activity = task_config.adb_launch_activity
                if activity:
                    component = activity if '/' in activity else f"{pkg}/{activity}"
                    launch_command = f"am start -n {component}"
                else:
                    launch_command = f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"
                logger.info(f"启动应用命令: {launch_command}")
                await self._run_adb_command(device_id, launch_command, task_config.id)
            return True
        except Exception as e:
            logger.error(f"ADB前置任务失败: {e}", exc_info=True)
            return False

    async def _ensure_adb_connection(self, device_id: str, task_id: Optional[str] = None) -> bool:
        """确保已通过 adb connect 连接到指定设备"""
        if device_id in self.connected_devices:
            return True

        adb_path = config_manager.get_config().app.adb_path or "adb"
        adb_exec = shlex.quote(adb_path)
        safe_device = shlex.quote(device_id)
        command = f"{adb_exec} connect {safe_device}"
        logger.info(f"尝试连接 ADB 设备: {device_id}")
        success, return_code, _, stderr = await self._run_shell_command(
            command,
            enable_global_log=False,
            task_id=task_id
        )
        if success:
            logger.info(f"ADB 设备 '{device_id}' 连接成功")
            self.connected_devices.add(device_id)
            return True

        logger.error(f"ADB 设备 '{device_id}' 连接失败 (返回码 {return_code}): {stderr}")
        return False

    async def _ensure_target_resolution(self, task_config: TaskConfig) -> bool:
        """在执行前确保设备分辨率符合任务要求"""
        device_id = task_config.adb_device_id
        target_raw = task_config.target_resolution or ""
        target = target_raw.lower().replace("×", "x").strip()

        if not device_id:
            logger.error(f"任务 '{task_config.name}' 配置了分辨率调整但缺少ADB设备ID")
            return False

        if "x" not in target:
            logger.error(f"任务 '{task_config.name}' 的目标分辨率格式无效: {target_raw}")
            return False

        if self.last_known_resolution == target:
            logger.debug(f"任务 '{task_config.name}' 所需分辨率 {target} 已生效，跳过调整")
            return True

        logger.info(
            "调整任务 '%s' 设备 %s 分辨率: %s -> %s",
            task_config.name,
            device_id,
            self.last_known_resolution or "未知",
            target
        )
        try:
            await self._run_adb_command(device_id, f"wm size {target}", task_config.id)
            self.last_known_resolution = target
            app_config = config_manager.get_config()
            if getattr(app_config.app, "last_device_resolution", None) != target:
                app_config.app.last_device_resolution = target
                config_manager.save_config(app_config)
            return True
        except Exception as e:
            logger.error(f"调整分辨率失败: {e}", exc_info=True)
            return False

    async def _execute_main_task(self, task_config: TaskConfig) -> Tuple[bool, int, str, str]:
        """执行主命令"""
        log_file = None
        if task_config.enable_temp_log:
            log_file = self._create_temp_log_file(task_config.id)
            self.temp_log_files[task_config.id] = log_file
        
        return await self._run_shell_command(
            task_config.main_command,
            log_file=log_file,
            enable_global_log=task_config.enable_global_log,
            task_id=task_config.id
        )

    async def _execute_post_tasks(self, task_config: TaskConfig, result: TaskResult):
        """执行后置任务，如日志扫描和发送通知"""
        log_content = ""
        if task_config.enable_temp_log and task_config.id in self.temp_log_files:
            try:
                with open(self.temp_log_files[task_config.id], 'r', encoding='utf-8') as f:
                    log_content = f.read()
            except Exception as e:
                logger.error(f"读取临时日志文件失败: {e}")
        
        # 如果没有临时日志，使用stdout/stderr
        if not log_content:
            log_content = result.stdout + "\n" + result.stderr

        # 1. 关键词监控
        matched_keywords = []
        if task_config.post_task.log_keywords:
            for keyword in task_config.post_task.log_keywords:
                if keyword in log_content:
                    matched_keywords.append(keyword)
        
        if matched_keywords:
            logger.info(f"任务 '{task_config.name}' 匹配到关键词: {', '.join(matched_keywords)}")
            cfg = task_config.post_task.keyword_notification
            if cfg:
                title = cfg.title.format(keywords=', '.join(matched_keywords))
                content = cfg.content.format(keywords=', '.join(matched_keywords))
                await notification_service.send_webhook_notification(title, content, cfg.tag)

        # 2. 推送成功/失败通知
        push_cfg = task_config.post_task.push_notification
        if not push_cfg.enabled:
            return

        should_notify = (result.success and push_cfg.on_success) or (not result.success and push_cfg.on_failure)

        if should_notify:
            status_str = "执行成功" if result.success else "执行失败"
            title = push_cfg.title or f"任务 {task_config.name} {status_str}"
            content = push_cfg.content or f"任务 '{task_config.name}' 已{status_str}。\n耗时: {result.duration:.2f}秒"
            tag = push_cfg.tag or ("task-success" if result.success else "task-failure")
            
            await notification_service.send_webhook_notification(title, content, tag)

    async def _run_adb_command(self, device_id: str, command: str, task_id: Optional[str] = None):
        """运行ADB命令并处理错误"""
        adb_path = config_manager.get_config().app.adb_path or "adb"
        adb_exec = shlex.quote(adb_path)
        safe_device = shlex.quote(device_id)
        full_command = f"{adb_exec} -s {safe_device} shell {command}"
        success, _, _, stderr = await self._run_shell_command(
            full_command,
            enable_global_log=False,
            task_id=task_id
        )
        if not success:
            raise Exception(f"ADB命令执行失败: {full_command}\n错误: {stderr}")

    async def _run_shell_command(
        self,
        command: str,
        log_file: Optional[Path] = None,
        enable_global_log: bool = True,
        task_id: Optional[str] = None
    ) -> Tuple[bool, int, str, str]:
        """健壮的 Shell 命令执行器"""
        logger.debug(f"Executing command: {command}")
        log_writer = None
        if log_file:
            try:
                log_writer = open(log_file, 'a', encoding='utf-8')
            except Exception as e:
                logger.error(f"无法打开临时日志文件 {log_file}: {e}")

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def read_stream(stream, stream_name, output_list):
            async for line_bytes in stream:
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                output_list.append(line)
                if enable_global_log:
                    if task_id:
                        logger.info(f"[{task_id}] [{stream_name}] {line}")
                    else:
                        logger.info(f"[{stream_name}] {line}")
                if log_writer:
                    log_writer.write(f"[{datetime.now().isoformat()}] [{stream_name}] {line}\n")
                    log_writer.flush()
                if task_id:
                    self._append_live_log(task_id, f"[{stream_name}] {line}")

        stdout_lines, stderr_lines = [], []
        try:
            await asyncio.gather(
                read_stream(process.stdout, "STDOUT", stdout_lines),
                read_stream(process.stderr, "STDERR", stderr_lines)
            )
            await process.wait()
        except asyncio.CancelledError:
            logger.warning(f"命令执行被取消: {command}")
            process.kill()
            await process.wait()
            raise
        finally:
            if log_writer:
                log_writer.close()

        return process.returncode == 0, process.returncode, "\n".join(stdout_lines), "\n".join(stderr_lines)

    def _create_temp_log_file(self, task_id: str) -> Path:
        log_dir = Path("logs/temp")
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"task_{task_id}_{timestamp}.log"
        return log_file

    async def cancel_task(self, task_id: str) -> bool:
        task = self.running_tasks.get(task_id)
        if not task:
            return False

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"任务 '{task_id}' 已成功取消")
        return True

    def get_task_status(self, task_id: str) -> TaskStatus:
        if task_id in self.running_tasks:
            return TaskStatus.RUNNING
        
        result = self.task_results.get(task_id)
        if not result:
            return TaskStatus.PENDING
        
        if result.message == "任务被取消":
            return TaskStatus.CANCELLED
        
        return TaskStatus.COMPLETED if result.success else TaskStatus.FAILED

    def get_running_tasks(self) -> list[str]:
        return list(self.running_tasks.keys())

    def get_temp_log_file(self, task_id: str) -> Optional[Path]:
        return self.temp_log_files.get(task_id)

    def _append_live_log(self, task_id: str, line: str):
        if task_id not in self.live_logs:
            self.live_logs[task_id] = deque(maxlen=500)
        self.live_logs[task_id].append(line)

    def get_live_logs(self, task_id: str, limit: int = 200) -> list[str]:
        if task_id not in self.live_logs:
            return []
        if limit <= 0:
            return list(self.live_logs[task_id])
        return list(self.live_logs[task_id])[-limit:]

    def get_task_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        if limit <= 0 or limit >= len(self.task_history):
            return list(self.task_history)[::-1]
        return list(self.task_history)[-limit:][::-1]

# 全局任务执行器实例
task_executor = TaskExecutor()