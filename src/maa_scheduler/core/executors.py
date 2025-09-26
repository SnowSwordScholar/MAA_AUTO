"""
任务执行器基类和具体实现
"""

import os
import subprocess
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path

class TaskExecutor(ABC):
    """任务执行器基类"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def execute_step(self, step_type: str, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行步骤"""
        pass
        
    @abstractmethod
    def get_supported_steps(self) -> List[str]:
        """获取支持的步骤类型"""
        pass

class ADBExecutor(TaskExecutor):
    """ADB任务执行器"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.current_resolution = None
        
    def get_supported_steps(self) -> List[str]:
        return ['adb_wake', 'adb_keep_awake', 'adb_start', 'adb_start_app', 'resolution', 'resolution_check']
        
    def execute_step(self, step_type: str, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行ADB相关步骤"""
        if step_type == 'adb_wake':
            return self._execute_adb_wake(params, options)
        elif step_type == 'adb_keep_awake':
            return self._execute_adb_keep_awake(params, options)
        elif step_type == 'adb_start':
            return self._execute_adb_start(params, options)
        elif step_type == 'adb_start_app':
            return self._execute_adb_start_app(params, options)
        elif step_type == 'resolution':
            return self._execute_resolution(params, options)
        elif step_type == 'resolution_check':
            return self._execute_resolution_check(params, options)
        else:
            return False, f"不支持的步骤类型: {step_type}"
            
    def _execute_adb_wake(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行ADB唤醒屏幕"""
        device = params[0] if params else self.config.get_env('ADB_DEVICE', 'localhost:35555')
        
        try:
            # 连接设备
            result = subprocess.run(['adb', 'connect', device], 
                                  check=True, capture_output=True, text=True, timeout=30)
            
            # 唤醒屏幕
            subprocess.run(['adb', '-s', device, 'shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'], 
                         check=True, capture_output=True, timeout=10)
            
            # 发送菜单键解锁
            subprocess.run(['adb', '-s', device, 'shell', 'input', 'keyevent', 'KEYCODE_MENU'], 
                         check=True, capture_output=True, timeout=10)
            
            success_msg = f"ADB唤醒屏幕成功: {device}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except subprocess.CalledProcessError as e:
            error_msg = f"ADB唤醒失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
        except subprocess.TimeoutExpired:
            error_msg = "ADB唤醒超时"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_adb_start(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行ADB启动应用"""
        if not params:
            return False, "缺少应用包名参数"
        
        app_component = params[0]
        device = self.config.get_env('ADB_DEVICE', 'localhost:35555')
        
        try:
            subprocess.run(['adb', '-s', device, 'shell', 'am', 'start', '-n', app_component], 
                         check=True, capture_output=True, timeout=30)
            
            success_msg = f"应用启动成功: {app_component}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except subprocess.CalledProcessError as e:
            error_msg = f"应用启动失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_resolution(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """设置屏幕分辨率"""
        if not params:
            return False, "缺少分辨率参数"
        
        resolution = params[0]
        
        # 检查是否需要设置（避免重复设置）
        if self.current_resolution == resolution:
            return True, f"分辨率已是 {resolution}"
        
        device = self.config.get_env('ADB_DEVICE', 'localhost:35555')
        
        try:
            subprocess.run(['adb', '-s', device, 'shell', 'wm', 'size', resolution], 
                         check=True, capture_output=True, timeout=10)
            
            self.current_resolution = resolution
            success_msg = f"分辨率设置成功: {resolution}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except subprocess.CalledProcessError as e:
            error_msg = f"分辨率设置失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_adb_keep_awake(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行ADB保持屏幕唤醒"""
        device = params[0] if params else self.config.get_env('ADB_DEVICE', 'localhost:35555')
        
        try:
            # 发送WAKEUP键唤醒屏幕
            subprocess.run(['adb', '-s', device, 'shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'], 
                         check=True, capture_output=True, timeout=10)
            
            # 稍等一下再发送MENU键保持唤醒
            import time
            time.sleep(0.5)
            subprocess.run(['adb', '-s', device, 'shell', 'input', 'keyevent', 'KEYCODE_MENU'], 
                         check=True, capture_output=True, timeout=10)
            
            success_msg = f"ADB保持屏幕唤醒成功: {device}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except subprocess.CalledProcessError as e:
            error_msg = f"ADB保持唤醒失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
        except subprocess.TimeoutExpired:
            error_msg = "ADB保持唤醒超时"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_adb_start_app(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行ADB启动应用 - 新版本"""
        if len(params) < 2:
            return False, "缺少设备和应用包名参数"
        
        device = params[0]
        app_component = params[1]
        
        try:
            subprocess.run(['adb', '-s', device, 'shell', 'am', 'start', '-n', app_component], 
                         check=True, capture_output=True, timeout=30)
            
            success_msg = f"应用启动成功: {app_component} (设备: {device})"
            self.logger.info(success_msg)
            return True, success_msg
            
        except subprocess.CalledProcessError as e:
            error_msg = f"应用启动失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_resolution_check(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """检查屏幕分辨率"""
        expected_resolution = params[0] if params else "1920x1080"
        device = self.config.get_env('ADB_DEVICE', 'localhost:35555')
        
        try:
            result = subprocess.run(['adb', '-s', device, 'shell', 'wm', 'size'], 
                                  check=True, capture_output=True, text=True, timeout=10)
            
            actual_resolution = result.stdout.strip()
            success_msg = f"设备分辨率检查: {actual_resolution} (期望: {expected_resolution})"
            self.logger.info(success_msg)
            return True, success_msg
            
        except subprocess.CalledProcessError as e:
            error_msg = f"分辨率检查失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg

class CommandExecutor(TaskExecutor):
    """命令执行器"""
    
    def get_supported_steps(self) -> List[str]:
        return ['command', 'wait']
        
    def execute_step(self, step_type: str, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行命令相关步骤"""
        if step_type == 'command':
            return self._execute_command(params, options)
        elif step_type == 'wait':
            return self._execute_wait(params, options)
        else:
            return False, f"不支持的步骤类型: {step_type}"
            
    def _execute_command(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行命令"""
        if not params:
            return False, "缺少命令参数"
        
        command = params[0]
        timeout = options.get('timeout', 1800)
        log_output = options.get('log', True)
        task_name = options.get('task_name', 'unknown')
        
        try:
            self.logger.info(f"开始执行命令: {command}")
            
            # 使用实时输出的方式执行命令
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            output_lines = []
            
            # 实时读取输出
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    if log_output:
                        self.logger.info(f"[{task_name}] {line}")
                    output_lines.append(line)
                    
                    # 实时关键词检测
                    self._check_keywords_in_line(line, task_name)
            
            # 等待进程结束
            return_code = process.wait(timeout=timeout)
            output = '\n'.join(output_lines)
            
            if return_code == 0:
                self.logger.info("命令执行成功")
                return True, output
            else:
                error_msg = f"命令执行失败，返回码: {return_code}"
                self.logger.error(error_msg)
                return False, f"{error_msg}\n{output}"
                
        except subprocess.TimeoutExpired:
            process.kill()
            error_msg = f"命令执行超时 ({timeout}秒)"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"命令执行异常: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_wait(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行等待"""
        if not params:
            return False, "缺少等待时间参数"
        
        try:
            wait_time = int(params[0])
            time.sleep(wait_time)
            return True, f"等待 {wait_time} 秒完成"
        except ValueError:
            return False, "等待时间参数无效"
            
    def _check_keywords_in_line(self, line: str, task_name: str):
        """检查日志行中的关键词"""
        # 这里可以集成关键词检测和WebHook通知功能
        # 暂时由调度器处理
        pass

class HttpExecutor(TaskExecutor):
    """HTTP请求执行器"""
    
    def get_supported_steps(self) -> List[str]:
        return ['http_get', 'http_post', 'webhook']
        
    def execute_step(self, step_type: str, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行HTTP相关步骤"""
        if step_type == 'http_get':
            return self._execute_http_get(params, options)
        elif step_type == 'http_post':
            return self._execute_http_post(params, options)
        elif step_type == 'webhook':
            return self._execute_webhook(params, options)
        else:
            return False, f"不支持的步骤类型: {step_type}"
            
    def _execute_http_get(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行HTTP GET请求"""
        if not params:
            return False, "缺少URL参数"
            
        import requests
        
        url = params[0]
        timeout = options.get('timeout', 30)
        
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            
            success_msg = f"HTTP GET成功: {url} (状态码: {response.status_code})"
            self.logger.info(success_msg)
            return True, response.text
            
        except requests.RequestException as e:
            error_msg = f"HTTP GET失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_http_post(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行HTTP POST请求"""
        if not params:
            return False, "缺少URL参数"
            
        import requests
        import json
        
        url = params[0]
        data = params[1] if len(params) > 1 else ""
        timeout = options.get('timeout', 30)
        
        try:
            # 尝试解析JSON数据
            json_data = None
            if data:
                try:
                    json_data = json.loads(data)
                except json.JSONDecodeError:
                    pass
            
            if json_data:
                response = requests.post(url, json=json_data, timeout=timeout)
            else:
                response = requests.post(url, data=data, timeout=timeout)
                
            response.raise_for_status()
            
            success_msg = f"HTTP POST成功: {url} (状态码: {response.status_code})"
            self.logger.info(success_msg)
            return True, response.text
            
        except requests.RequestException as e:
            error_msg = f"HTTP POST失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_webhook(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行WebHook通知"""
        if not params:
            return False, "缺少模板名称参数"
            
        template_name = params[0]
        message = params[1] if len(params) > 1 else ""
        
        # 获取WebHook模板
        templates = self.config.get_webhook_templates()
        if template_name not in templates:
            return False, f"未找到WebHook模板: {template_name}"
        
        template = templates[template_name]
        
        # 构建WebHook URL
        webhook_url = self.config.get_env('WEBHOOK_BASE_URL', '')
        if not webhook_url:
            return False, "未配置WebHook URL"
        
        # 替换URL中的占位符
        webhook_url = webhook_url.replace('[uid]', self.config.get_env('WEBHOOK_UID', ''))
        webhook_url = webhook_url.replace('[token]', self.config.get_env('WEBHOOK_TOKEN', ''))
        
        # 准备消息内容
        title = template['title']
        description = f"{template['description']}\n\n{message}" if message else template['description']
        
        try:
            import requests
            
            params_dict = {
                'title': title,
                'desp': description,
                'tags': template['tags']
            }
            
            response = requests.get(webhook_url, params=params_dict, timeout=10)
            response.raise_for_status()
            
            success_msg = f"WebHook通知发送成功: {template_name}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"WebHook通知发送失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg

class FileExecutor(TaskExecutor):
    """文件操作执行器"""
    
    def get_supported_steps(self) -> List[str]:
        return ['file_write', 'file_read', 'file_copy', 'file_delete']
        
    def execute_step(self, step_type: str, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """执行文件相关步骤"""
        if step_type == 'file_write':
            return self._execute_file_write(params, options)
        elif step_type == 'file_read':
            return self._execute_file_read(params, options)
        elif step_type == 'file_copy':
            return self._execute_file_copy(params, options)
        elif step_type == 'file_delete':
            return self._execute_file_delete(params, options)
        else:
            return False, f"不支持的步骤类型: {step_type}"
            
    def _execute_file_write(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """写入文件"""
        if len(params) < 2:
            return False, "缺少文件路径和内容参数"
        
        file_path = Path(params[0])
        content = params[1]
        encoding = options.get('encoding', 'utf-8')
        
        try:
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            
            success_msg = f"文件写入成功: {file_path}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"文件写入失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_file_read(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """读取文件"""
        if not params:
            return False, "缺少文件路径参数"
        
        file_path = Path(params[0])
        encoding = options.get('encoding', 'utf-8')
        
        try:
            if not file_path.exists():
                return False, f"文件不存在: {file_path}"
            
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            
            success_msg = f"文件读取成功: {file_path} ({len(content)}字符)"
            self.logger.info(success_msg)
            return True, content
            
        except Exception as e:
            error_msg = f"文件读取失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_file_copy(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """复制文件"""
        if len(params) < 2:
            return False, "缺少源文件和目标文件参数"
        
        src_path = Path(params[0])
        dst_path = Path(params[1])
        
        try:
            import shutil
            
            if not src_path.exists():
                return False, f"源文件不存在: {src_path}"
            
            # 确保目标目录存在
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(src_path, dst_path)
            
            success_msg = f"文件复制成功: {src_path} -> {dst_path}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"文件复制失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def _execute_file_delete(self, params: List[str], options: Dict[str, Any]) -> Tuple[bool, str]:
        """删除文件"""
        if not params:
            return False, "缺少文件路径参数"
        
        file_path = Path(params[0])
        
        try:
            if not file_path.exists():
                return True, f"文件不存在: {file_path}"
            
            file_path.unlink()
            
            success_msg = f"文件删除成功: {file_path}"
            self.logger.info(success_msg)
            return True, success_msg
            
        except Exception as e:
            error_msg = f"文件删除失败: {e}"
            self.logger.error(error_msg)
            return False, error_msg