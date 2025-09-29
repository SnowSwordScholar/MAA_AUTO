"""
任务执行器模块
处理任务的执行、前置后置处理、日志管理等
"""

import asyncio
import subprocess
import os
import logging
import tempfile
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from .config import TaskConfig, config_manager
from .notification import notification_service

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消

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
        self.temp_log_files: Dict[str, str] = {}
    
    async def execute_task(self, task_config: TaskConfig) -> TaskResult:
        """执行任务"""
        logger.info(f"开始执行任务: {task_config.name} (ID: {task_config.id})")
        
        result = TaskResult(task_config.id, False)
        result.start_time = datetime.now()
        
        try:
            # 发送开始通知
            await notification_service.notify_task_started(task_config.name, task_config.id)
            
            # 执行前置任务
            if not await self._execute_pre_tasks(task_config):
                result.message = "前置任务执行失败"
                return result
            
            # 执行主任务
            success, return_code, stdout, stderr = await self._execute_main_task(task_config)
            
            result.success = success
            result.return_code = return_code
            result.stdout = stdout
            result.stderr = stderr
            
            if success:
                result.message = "任务执行成功"
                logger.info(f"任务执行成功: {task_config.name}")
            else:
                result.message = f"任务执行失败，返回码: {return_code}"
                logger.error(f"任务执行失败: {task_config.name}, 返回码: {return_code}")
            
            # 执行后置任务
            await self._execute_post_tasks(task_config, result)
            
        except Exception as e:
            result.success = False
            result.message = f"任务执行异常: {str(e)}"
            logger.error(f"任务执行异常: {task_config.name}, 错误: {e}", exc_info=True)
        
        finally:
            result.end_time = datetime.now()
            if result.start_time:
                result.duration = (result.end_time - result.start_time).total_seconds()
            
            # 清理临时资源
            await self._cleanup_task_resources(task_config.id)
            
            # 存储结果
            self.task_results[task_config.id] = result
            
        return result
    
    async def _execute_pre_tasks(self, task_config: TaskConfig) -> bool:
        """执行前置任务"""
        try:
            # MAA任务的ADB前置处理
            if task_config.task_type == "maa" and task_config.enable_adb_wakeup:
                logger.info(f"执行MAA任务ADB前置处理: {task_config.name}")
                
                # 获取设备ID，如果没有配置则使用默认值
                device_id = getattr(task_config, 'emulator_device_id', '127.0.0.1:5555')
                
                try:
                    # 唤醒设备屏幕
                    logger.info(f"唤醒设备屏幕: {device_id}")
                    await self._run_adb_command(device_id, "input keyevent KEYCODE_WAKEUP")
                    await asyncio.sleep(1)
                    
                    # 设置分辨率（如果配置了）
                    target_resolution = getattr(task_config, 'target_resolution', None)
                    if target_resolution and 'x' in target_resolution:
                        logger.info(f"设置屏幕分辨率: {target_resolution}")
                        width, height = target_resolution.split('x')
                        await self._run_adb_command(
                            device_id, 
                            f"shell wm size {width}x{height}"
                        )
                        await asyncio.sleep(2)
                    
                    logger.info("ADB前置处理完成")
                    
                except Exception as adb_error:
                    logger.warning(f"ADB前置处理失败，但继续执行任务: {adb_error}")
                    # ADB失败不影响主任务执行，只记录警告
            
            return True
            
        except Exception as e:
            logger.error(f"前置任务执行异常: {e}", exc_info=True)
            return False
    
    async def _execute_main_task(self, task_config: TaskConfig) -> Tuple[bool, int, str, str]:
        """执行主任务"""
        logger.info(f"执行主任务: {task_config.main_command}")
        
        # 设置工作目录（使用当前目录作为默认值）
        cwd = getattr(task_config, 'working_directory', os.getcwd())
        
        # 设置环境变量
        env = os.environ.copy()
        env_vars = getattr(task_config, 'environment_variables', {})
        env.update(env_vars)
        
        # 设置日志文件
        temp_log_file = None
        if task_config.enable_temp_log:
            # 总是创建新的临时日志文件
            temp_log_file = self._create_temp_log_file(task_config.id)
            self.temp_log_files[task_config.id] = temp_log_file
        
        # 执行命令
        return await self._run_shell_command(
            task_config.main_command,
            cwd=cwd,
            env=env,
            log_file=temp_log_file,
            enable_global_log=task_config.enable_global_log
        )
    
    async def _execute_post_tasks(self, task_config: TaskConfig, result: TaskResult):
        """执行后置任务"""
        try:
            # 准备通知变量
            variables = {
                'task_name': task_config.name,
                'timestamp': result.end_time.strftime('%Y-%m-%d %H:%M:%S') if result.end_time else '',
                'duration': f"{result.duration:.2f}秒" if result.duration else '',
                'output': result.stdout[:500] + '...' if len(result.stdout) > 500 else result.stdout,
                'error_message': result.stderr[:300] + '...' if len(result.stderr) > 300 else result.stderr,
            }
            
            # 发送任务完成通知
            if result.success and hasattr(task_config, 'post_task') and task_config.post_task and task_config.post_task.notify_on_success:
                logger.info(f"发送成功通知: {task_config.name}")
                await self._send_notification(task_config.post_task.success_notification, variables)
            
            elif not result.success and hasattr(task_config, 'post_task') and task_config.post_task and task_config.post_task.notify_on_failure:
                logger.info(f"发送失败通知: {task_config.name}")
                await self._send_notification(task_config.post_task.failure_notification, variables)
            
            # 检查关键词匹配
            if (hasattr(task_config, 'post_task') and task_config.post_task and 
                task_config.post_task.enable_keyword_monitoring and task_config.post_task.log_keywords):
                await self._check_log_keywords(task_config, result, variables)
        
        except Exception as e:
            logger.error(f"后置任务执行异常: {e}", exc_info=True)
    
    async def _send_notification(self, notification_config, variables):
        """发送通知"""
        if not notification_config:
            return
            
        try:
            # 替换变量
            title = self._replace_variables(notification_config.title, variables)
            content = self._replace_variables(notification_config.content, variables)
            
            # 发送通知
            await notification_service.send_notification(
                title=title,
                content=content,
                tags=notification_config.tag.split(',') if notification_config.tag else []
            )
        except Exception as e:
            logger.error(f"发送通知失败: {e}")
    
    def _replace_variables(self, text: str, variables: Dict[str, str]) -> str:
        """替换变量"""
        if not text:
            return ""
        
        result = text
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result
    
    async def _check_log_keywords(self, task_config: TaskConfig, result: TaskResult, variables: Dict[str, str]):
        """检查日志关键词"""
        try:
            log_content = ""
            
            # 获取日志内容
            if task_config.id in self.temp_log_files:
                temp_log_file = self.temp_log_files[task_config.id]
                if os.path.exists(temp_log_file):
                    with open(temp_log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        log_content = f.read()
            
            # 如果没有临时日志，使用 stdout/stderr
            if not log_content:
                log_content = result.stdout + "\n" + result.stderr
            
            # 检查关键词
            matched_keywords = []
            matched_lines = []
            
            for line in log_content.split('\n'):
                for keyword in task_config.post_task.log_keywords:
                    if keyword.strip().lower() in line.lower():
                        if keyword not in matched_keywords:
                            matched_keywords.append(keyword)
                        matched_lines.append(line.strip())
            
            # 发送关键词匹配通知
            if matched_keywords:
                logger.info(f"检测到关键词匹配: {matched_keywords}")
                
                # 更新变量
                keyword_variables = variables.copy()
                keyword_variables.update({
                    'matched_keywords': ', '.join(matched_keywords),
                    'matched_lines': '\n'.join(matched_lines[:5]),  # 最多显示5行
                    'keywords': ', '.join(matched_keywords)  # 向后兼容
                })
                
                await self._send_notification(
                    task_config.post_task.keyword_notification,
                    keyword_variables
                )
        
        except Exception as e:
            logger.error(f"关键词检查异常: {e}", exc_info=True)
    
    async def _run_adb_command(self, device_id: str, command: str) -> bool:
        """运行 ADB 命令"""
        full_command = f"adb -s {device_id} {command}"
        success, return_code, stdout, stderr = await self._run_shell_command(full_command)
        
        if not success:
            logger.error(f"ADB 命令执行失败: {full_command}, 返回码: {return_code}")
            logger.error(f"错误输出: {stderr}")
        
        return success
    
    async def _run_shell_command(
        self,
        command: str,
        cwd: str = None,
        env: Dict[str, str] = None,
        log_file: str = None,
        enable_global_log: bool = True
    ) -> Tuple[bool, int, str, str]:
        """运行 Shell 命令"""
        try:
            # 创建进程
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env
            )
            
            # 实时读取输出
            stdout_lines = []
            stderr_lines = []
            
            async def read_stream(stream, lines_list, stream_name):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    
                    line_str = line.decode('utf-8', errors='ignore').rstrip()
                    lines_list.append(line_str)
                    
                    # 全局日志输出
                    if enable_global_log:
                        logger.info(f"[{stream_name}] {line_str}")
                    
                    # 临时日志文件
                    if log_file:
                        try:
                            with open(log_file, 'a', encoding='utf-8') as f:
                                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{stream_name}] {line_str}\n")
                                f.flush()
                        except Exception as e:
                            logger.error(f"写入临时日志失败: {e}")
            
            # 并行读取 stdout 和 stderr
            await asyncio.gather(
                read_stream(process.stdout, stdout_lines, "STDOUT"),
                read_stream(process.stderr, stderr_lines, "STDERR")
            )
            
            # 等待进程结束
            return_code = await process.wait()
            
            stdout = "\n".join(stdout_lines)
            stderr = "\n".join(stderr_lines)
            success = return_code == 0
            
            return success, return_code, stdout, stderr
            
        except Exception as e:
            logger.error(f"命令执行异常: {command}, 错误: {e}", exc_info=True)
            return False, -1, "", str(e)
    
    def _create_temp_log_file(self, task_id: str) -> str:
        """创建临时日志文件"""
        log_dir = Path("logs/temp")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"task_{task_id}_{timestamp}.log"
        
        return str(log_file)
    
    async def _cleanup_task_resources(self, task_id: str):
        """清理任务资源"""
        try:
            # 从运行任务列表中移除
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            # 可选择性清理临时日志文件
            # 这里我们保留临时日志文件，以供后续查看
            # if task_id in self.temp_log_files:
            #     temp_log_file = self.temp_log_files[task_id]
            #     if os.path.exists(temp_log_file):
            #         os.remove(temp_log_file)
            #     del self.temp_log_files[task_id]
            
        except Exception as e:
            logger.error(f"清理任务资源异常: {e}", exc_info=True)
    
    async def start_task_async(self, task_config: TaskConfig) -> str:
        """异步启动任务"""
        if task_config.id in self.running_tasks:
            raise ValueError(f"任务 {task_config.id} 已在运行中")
        
        # 创建异步任务
        async_task = asyncio.create_task(self.execute_task(task_config))
        self.running_tasks[task_config.id] = async_task
        
        logger.info(f"任务已启动: {task_config.name} (ID: {task_config.id})")
        return task_config.id
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.running_tasks:
            return False
        
        task = self.running_tasks[task_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        logger.info(f"任务已取消: {task_id}")
        return True
    
    def get_task_status(self, task_id: str) -> TaskStatus:
        """获取任务状态"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            if task.done():
                if task.cancelled():
                    return TaskStatus.CANCELLED
                else:
                    result = self.task_results.get(task_id)
                    if result:
                        return TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                    return TaskStatus.FAILED
            else:
                return TaskStatus.RUNNING
        elif task_id in self.task_results:
            result = self.task_results[task_id]
            return TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        else:
            return TaskStatus.PENDING
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        return self.task_results.get(task_id)
    
    def get_running_tasks(self) -> List[str]:
        """获取正在运行的任务"""
        running = []
        for task_id, task in self.running_tasks.items():
            if not task.done():
                running.append(task_id)
        return running
    
    def get_temp_log_file(self, task_id: str) -> Optional[str]:
        """获取临时日志文件路径"""
        return self.temp_log_files.get(task_id)

# 全局任务执行器实例
task_executor = TaskExecutor()