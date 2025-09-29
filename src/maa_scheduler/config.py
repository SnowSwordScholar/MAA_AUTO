"""
配置管理模块
处理应用配置、环境变量、任务配置等
"""

import os
import yaml
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class WebhookConfig(BaseModel):
    """Webhook 推送配置"""
    uid: str = Field(..., description="推送 UID")
    token: str = Field(..., description="推送令牌")
    base_url: str = Field(..., description="推送基础 URL")

class ResourceGroup(BaseModel):
    """资源分组配置"""
    name: str = Field(..., description="分组名称")
    description: str = Field(default="", description="分组描述")
    max_concurrent: int = Field(default=1, description="最大并发任务数")
    resources: List[str] = Field(default_factory=list, description="资源列表")

class NotificationConfig(BaseModel):
    """通知配置"""
    title: str = "MAA调度器通知"
    tag: str = "maa-scheduler" 
    content: str = "任务状态更新"

class LogConfig(BaseModel):
    """日志配置"""
    enable_global_log: bool = True
    enable_temp_log: bool = False

class NotificationsConfig(BaseModel):
    """通知配置组"""
    notify_on_success: bool = False
    notify_on_failure: bool = True
    success_notification: Optional[NotificationConfig] = None
    failure_notification: Optional[NotificationConfig] = None

class KeywordMonitoring(BaseModel):
    """关键词监控配置"""
    enabled: bool = False
    keywords: List[str] = Field(default_factory=list)
    notification: Optional[NotificationConfig] = None

class PostTaskConfig(BaseModel):
    """后置任务配置"""
    log_config: LogConfig = Field(default_factory=LogConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig) 
    keyword_monitoring: KeywordMonitoring = Field(default_factory=KeywordMonitoring)

class ExecutionConfig(BaseModel):
    """执行配置"""
    command: str
    enable_adb_wakeup: bool = False
    adb_device_id: Optional[str] = None

class TriggerConfig(BaseModel):
    """触发器配置"""
    trigger_type: Literal["scheduled", "interval", "random_time"]
    
    # 定时执行：支持在用户设定的固定时间段内执行任务（例如，每天 9:00-18:00）
    start_time: Optional[str] = None  # 开始时间，如 "09:00"
    end_time: Optional[str] = None    # 结束时间，如 "18:00"
    cron_expression: Optional[str] = None  # 精确定时使用cron表达式
    
    # 间隔执行：基于上次执行完成时间，在设定的间隔后再次执行（例如，每 2 小时执行一次）
    interval_minutes: Optional[int] = None  # 间隔分钟数
    
    # 随机时间执行：在用户设定的时间段内（如 10:00-12:00），随机选择一个时间点执行
    random_start_time: Optional[str] = None  # 随机开始时间，如 "10:00"
    random_end_time: Optional[str] = None    # 随机结束时间，如 "12:00"
    random_distribution: Literal["uniform", "normal"] = "uniform"

class TaskConfig(BaseModel):
    """任务配置"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    enabled: bool = True
    
    # 优先级和资源配置
    priority: int = Field(default=5, ge=1, le=10)
    resource_group: str = "default"
    
    # 任务类型：控制台任务 或 MAA任务
    task_type: Literal["console", "maa"] = "console"
    
    # 触发器配置
    trigger: TriggerConfig
    
    # 执行配置
    execution: Optional[ExecutionConfig] = None
    
    # 后置任务配置
    post_task: PostTaskConfig = Field(default_factory=PostTaskConfig)
    
    # === 兼容字段（向后兼容旧配置） ===
    # 执行配置：直接为命令（支持复杂的MAA命令）
    main_command: Optional[str] = None
    working_directory: Optional[str] = None
    environment_variables: Dict[str, str] = Field(default_factory=dict)
    
    # 前置任务配置（针对MAA任务）
    enable_adb_wakeup: bool = False  # MAA任务是否启用ADB唤醒屏幕
    emulator_device_id: Optional[str] = None
    target_resolution: Optional[str] = None
    startup_app: Optional[str] = None
    
    # 日志配置
    enable_global_log: bool = True
    enable_temp_log: bool = False  # 临时日志选项
    temp_log_path: Optional[str] = None
    
    # 其他兼容字段（向后兼容旧配置）
    is_emulator_task: Optional[bool] = None
    pre_commands: List[str] = Field(default_factory=list)
    notify_on_success: bool = False
    notify_on_failure: bool = True
    success_message: str = ""
    failure_message: str = ""
    keyword_notification: bool = False
    keyword_message: str = ""
    log_keywords: List[str] = Field(default_factory=list)
    
    def get_execution_command(self) -> str:
        """获取执行命令（兼容新旧配置）"""
        if self.execution:
            return self.execution.command
        return self.main_command or ""
    
    def get_adb_wakeup_enabled(self) -> bool:
        """获取ADB唤醒是否启用（兼容新旧配置）"""
        if self.execution:
            return self.execution.enable_adb_wakeup
        return self.enable_adb_wakeup
    
    def get_adb_device_id(self) -> Optional[str]:
        """获取ADB设备ID（兼容新旧配置）"""
        if self.execution:
            return self.execution.adb_device_id
        return self.emulator_device_id

class AppConfig(BaseModel):
    """应用配置"""
    # 基础配置
    app_name: str = Field(default="MAA Scheduler", description="应用名称")
    version: str = Field(default="0.1.0", description="版本号")
    debug: bool = Field(default=False, description="调试模式")
    
    # Web 配置
    web_host: str = Field(default="127.0.0.1", description="Web 服务主机")
    web_port: int = Field(default=8080, description="Web 服务端口")
    
    # 调度器配置
    scheduler_enabled: bool = Field(default=True, description="调度器是否启用")
    max_workers: int = Field(default=4, description="最大工作线程数")
    task_timeout: int = Field(default=3600, description="任务超时时间(秒)")
    
    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_file: str = Field(default="logs/maa_scheduler.log", description="日志文件路径")
    log_max_size: str = Field(default="10MB", description="日志文件最大大小")
    log_backup_count: int = Field(default=5, description="日志备份数量")
    
    # Webhook 配置
    webhook: Optional[WebhookConfig] = None
    
    # 资源分组
    resource_groups: List[ResourceGroup] = Field(default_factory=list)
    
    # 任务配置
    tasks: List[TaskConfig] = Field(default_factory=list)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: Path = None):
        if config_dir is None:
            config_dir = Path.cwd() / "config"
        
        self.config_dir = config_dir
        self.config_dir.mkdir(exist_ok=True)
        
        self.app_config_file = self.config_dir / "app.yaml"
        self.tasks_config_file = self.config_dir / "tasks.yaml"
        
        self._app_config: Optional[AppConfig] = None
    
    def load_webhook_config(self) -> Optional[WebhookConfig]:
        """从环境变量加载 Webhook 配置"""
        uid = os.getenv("WEBHOOK_UID")
        token = os.getenv("WEBHOOK_TOKEN")
        base_url = os.getenv("WEBHOOK_BASE_URL")
        
        if uid and token and base_url:
            return WebhookConfig(uid=uid, token=token, base_url=base_url)
        return None
    
    def load_app_config(self) -> AppConfig:
        """加载应用配置"""
        if self._app_config is not None:
            return self._app_config
        
        config_data = {}
        if self.app_config_file.exists():
            with open(self.app_config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
        
        # 添加 Webhook 配置
        webhook_config = self.load_webhook_config()
        if webhook_config:
            config_data["webhook"] = webhook_config.dict()
        
        # 创建默认资源分组
        if "resource_groups" not in config_data:
            config_data["resource_groups"] = [
                {
                    "name": "camera",
                    "description": "摄像头资源组",
                    "max_concurrent": 1,
                    "resources": ["camera", "adb"]
                },
                {
                    "name": "gpu",
                    "description": "GPU 资源组",
                    "max_concurrent": 1,
                    "resources": ["gpu", "cuda"]
                },
                {
                    "name": "general",
                    "description": "通用资源组",
                    "max_concurrent": 2,
                    "resources": []
                }
            ]
        
        self._app_config = AppConfig(**config_data)
        return self._app_config
    
    def save_app_config(self, config: AppConfig = None):
        """保存应用配置"""
        if config is None:
            config = self._app_config
        
        if config is None:
            return
        
        # 移除 webhook 配置（因为它来自环境变量）
        config_dict = config.dict()
        if "webhook" in config_dict:
            del config_dict["webhook"]
        
        with open(self.app_config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
        
        self._app_config = config
    
    def load_tasks_config(self) -> List[TaskConfig]:
        """加载任务配置"""
        if not self.tasks_config_file.exists():
            return []
        
        with open(self.tasks_config_file, 'r', encoding='utf-8') as f:
            tasks_data = yaml.safe_load(f) or []
        
        return [TaskConfig(**task_data) for task_data in tasks_data]
    
    def save_tasks_config(self, tasks: List[TaskConfig]):
        """保存任务配置"""
        tasks_data = [task.dict() for task in tasks]
        
        with open(self.tasks_config_file, 'w', encoding='utf-8') as f:
            yaml.dump(tasks_data, f, default_flow_style=False, allow_unicode=True)
    
    def get_resource_group(self, name: str) -> Optional[ResourceGroup]:
        """获取资源分组"""
        config = self.load_app_config()
        for group in config.resource_groups:
            if group.name == name:
                return group
        return None
    
    def add_task(self, task: TaskConfig):
        """添加任务"""
        tasks = self.load_tasks_config()
        
        # 检查 ID 是否已存在
        for existing_task in tasks:
            if existing_task.id == task.id:
                raise ValueError(f"任务 ID '{task.id}' 已存在")
        
        tasks.append(task)
        self.save_tasks_config(tasks)
    
    def update_task(self, task: TaskConfig):
        """更新任务"""
        tasks = self.load_tasks_config()
        
        for i, existing_task in enumerate(tasks):
            if existing_task.id == task.id:
                tasks[i] = task
                self.save_tasks_config(tasks)
                return
        
        raise ValueError(f"任务 ID '{task.id}' 不存在")
    
    def delete_task(self, task_id: str):
        """删除任务"""
        tasks = self.load_tasks_config()
        tasks = [task for task in tasks if task.id != task_id]
        self.save_tasks_config(tasks)
    
    def get_task(self, task_id: str) -> Optional[TaskConfig]:
        """获取任务"""
        tasks = self.load_tasks_config()
        for task in tasks:
            if task.id == task_id:
                return task
        return None

# 全局配置管理器实例
config_manager = ConfigManager()