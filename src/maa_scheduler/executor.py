"""
任务执行器模块
处理任务的执行、前置后置处理、日志管理等
"""

import asyncio
import subprocess
import os
import logging
import shlex
from collections import deque
from pathlib import Path
from typing import Dict, Optional, Tuple
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
        self.live_logs: Dict[str, deque[str]] = {}
    
    async def execute_task(self, task_config: TaskConfig):
        """执行任务的完整流程"""
        logger.info(f"开始执行任务: {task_config.name} (ID: {task_config.id})")

        result = TaskResult(task_config.id, False)
        result.start_time = datetime.now()
        
        # 将任务标记为正在运行
        task_future = asyncio.Future()
        self.running_tasks[task_config.id] = task_future
        self.live_logs[task_config.id] = deque(maxlen=500)

        try:
            # 1. 前置任务
            pre_task_success = await self._execute_pre_tasks(task_config)
            if not pre_task_success:
                raise Exception("前置任务执行失败")

            # 2. 主任务
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

            # 3. 后置任务
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
            if task_config.id in self.running_tasks:
                self.running_tasks.pop(task_config.id)
            
            # 标记任务已完成
            task_future.set_result(None)

    async def _execute_pre_tasks(self, task_config: TaskConfig) -> bool:
        """执行前置任务，如ADB唤醒"""
        if not task_config.enable_adb_wakeup:
            return True
        
        device_id = task_config.adb_device_id
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
            return True
        except Exception as e:
            logger.error(f"ADB前置任务失败: {e}", exc_info=True)
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
        full_command = f"{adb_exec} -s {device_id} {command}"
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
        if task_id not in self.running_tasks:
            return False
        
        task_future = self.running_tasks[task_id]
        task_future.cancel()
        try:
            await task_future
        except asyncio.CancelledError:
            logger.info(f"任务 '{task_id}' 已成功取消")
        finally:
            if task_id in self.running_tasks:
                self.running_tasks.pop(task_id)
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

# 全局任务执行器实例
task_executor = TaskExecutor()