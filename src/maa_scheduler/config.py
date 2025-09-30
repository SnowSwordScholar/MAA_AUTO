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

class NotificationConfig(BaseModel):
    """通知开关配置"""
    notify_on_startup: bool = Field(default=False, description="启动时通知")
    notify_on_shutdown: bool = Field(default=False, description="关闭时通知")

class AppSettings(BaseModel):
    """应用设置"""
    mode: Literal["scheduler", "single_task"] = Field(default="scheduler", description="调度器模式")
    task_timeout: int = Field(default=3600, description="任务超时时间(秒)")
    notification: NotificationConfig = Field(default_factory=NotificationConfig, description="通知设置")

class WebSettings(BaseModel):
    """Web界面配置"""
    host: str = Field(default="127.0.0.1", description="Web服务主机")
    port: int = Field(default=8080, description="Web服务端口")
    debug: bool = Field(default=False, description="调试模式")

class LoggingSettings(BaseModel):
    """日志配置"""
    level: str = Field(default="INFO", description="日志级别")
    file: str = Field(default="logs/maa_scheduler.log", description="日志文件路径")
    max_size: str = Field(default="10MB", description="日志文件最大大小")
    backup_count: int = Field(default=5, description="日志备份数量")

class WebhookConfig(BaseModel):
    """Webhook 配置"""
    uid: str
    token: str
    base_url: str

class ResourceGroup(BaseModel):
    """资源分组配置"""
    name: str = Field(..., description="分组名称")
    description: str = Field(default="", description="分组描述")
    max_concurrent: int = Field(default=1, description="最大并发任务数")

class TriggerConfig(BaseModel):
    """触发器配置"""
    trigger_type: Literal["scheduled", "interval", "random_time"] = Field(..., description="触发器类型")
    
    # 定时执行 (scheduled)
    start_time: Optional[str] = Field(default=None, description="开始时间, 格式 HH:MM")
    end_time: Optional[str] = Field(default=None, description="结束时间, 格式 HH:MM")
    
    # 间隔执行 (interval)
    interval_minutes: Optional[int] = Field(default=None, description="间隔分钟数")
    
    # 随机时间执行 (random_time)
    random_start_time: Optional[str] = Field(default=None, description="随机开始时间, 格式 HH:MM")
    random_end_time: Optional[str] = Field(default=None, description="随机结束时间, 格式 HH:MM")

class KeywordNotificationConfig(BaseModel):
    """关键词匹配通知配置"""
    title: str = Field(default="关键词匹配通知", description="通知标题")
    tag: str = Field(default="keyword-match", description="通知Tag")
    content: str = Field(default="在任务日志中匹配到关键词: {keywords}", description="通知内容模板")

class PostTaskAction(BaseModel):
    """后置任务动作"""
    enabled: bool = Field(default=False, description="是否启用")
    on_success: bool = Field(default=True, description="成功时触发")
    on_failure: bool = Field(default=True, description="失败时触发")
    title: Optional[str] = Field(default=None, description="自定义通知标题")
    tag: Optional[str] = Field(default=None, description="自定义通知Tag")
    content: Optional[str] = Field(default=None, description="自定义通知内容")

class PostTaskConfig(BaseModel):
    """后置任务配置"""
    log_keywords: List[str] = Field(default_factory=list, description="要监控的日志关键词")
    keyword_notification: Optional[KeywordNotificationConfig] = Field(default=None, description="关键词匹配通知配置")
    push_notification: PostTaskAction = Field(default_factory=PostTaskAction, description="推送通知动作")

class TaskConfig(BaseModel):
    """任务配置"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="任务唯一ID")
    name: str = Field(..., description="任务名称")
    description: str = Field(default="", description="任务描述")
    enabled: bool = Field(default=True, description="是否启用")
    
    priority: int = Field(default=5, ge=1, le=10, description="任务优先级 (1-10)")
    resource_group: str = Field(default="default", description="所属资源组")
    
    main_command: str = Field(..., description="要执行的主命令")
    
    # 前置任务
    enable_adb_wakeup: bool = Field(default=False, description="是否启用ADB唤醒屏幕")
    adb_device_id: Optional[str] = Field(default=None, description="ADB设备ID")
    
    # 日志选项
    enable_global_log: bool = Field(default=True, description="是否输出到全局日志")
    enable_temp_log: bool = Field(default=False, description="是否记录到临时日志")
    
    trigger: TriggerConfig = Field(..., description="触发器配置")
    post_task: PostTaskConfig = Field(default_factory=PostTaskConfig, description="后置任务配置")

class AppConfig(BaseModel):
    """根配置模型"""
    app: AppSettings = Field(default_factory=AppSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    resource_groups: List[ResourceGroup] = Field(default_factory=list)
    tasks: List[TaskConfig] = Field(default_factory=list)
    
    webhook: Optional[WebhookConfig] = None

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Path = None, tasks_path: Path = None):
        if config_path is None:
            config_path = Path.cwd() / "config" / "config.yaml"
        if tasks_path is None:
            tasks_path = Path.cwd() / "config" / "tasks.yaml"
        
        self.config_path = config_path
        self.tasks_path = tasks_path
        
        self.config_path.parent.mkdir(exist_ok=True)
        
        self._config: Optional[AppConfig] = None

    def load_config(self) -> AppConfig:
        """加载主配置和任务配置"""
        if self._config:
            return self._config

        config_data = {}
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}

        tasks_data = []
        if self.tasks_path.exists():
            with open(self.tasks_path, 'r', encoding='utf-8') as f:
                tasks_config = yaml.safe_load(f) or {}
        
        # 如果 tasks.yaml 的根就是一个列表，将其包装在 'tasks' 键下
        if isinstance(tasks_config, list):
            tasks_data = {"tasks": tasks_config}
        else:
            tasks_data = tasks_config
        
        # 合并配置
        config_data.update(tasks_data)

        # 加载 Webhook 配置
        webhook_config = self._load_webhook_from_env()
        if webhook_config:
            config_data["webhook"] = webhook_config.dict()

        self._config = AppConfig(**config_data)
        return self._config

    def save_config(self, config: AppConfig):
        """保存主配置和任务配置"""
        self._config = config
        
        # 分离主配置和任务配置
        main_config_dict = config.dict(exclude={'tasks', 'webhook'}, exclude_none=True)
        tasks_dict = {"tasks": [task.dict(exclude_none=True) for task in config.tasks]}

        # 保存主配置文件
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(main_config_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
        # 保存任务配置文件
        with open(self.tasks_path, 'w', encoding='utf-8') as f:
            yaml.dump(tasks_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def get_config(self) -> AppConfig:
        """获取当前加载的配置"""
        return self.load_config()

    def _load_webhook_from_env(self) -> Optional[WebhookConfig]:
        """从环境变量加载 Webhook 配置"""
        uid = os.getenv("WEBHOOK_UID")
        token = os.getenv("WEBHOOK_TOKEN")
        base_url = os.getenv("WEBHOOK_BASE_URL")
        
        if uid and token and base_url:
            return WebhookConfig(uid=uid, token=token, base_url=base_url)
        return None

    def get_task(self, task_id: str) -> Optional[TaskConfig]:
        """通过ID获取任务"""
        config = self.get_config()
        for task in config.tasks:
            if task.id == task_id:
                return task
        return None

    def add_task(self, task: TaskConfig):
        """添加一个新任务"""
        config = self.get_config()
        if any(t.id == task.id for t in config.tasks):
            raise ValueError(f"任务 ID '{task.id}' 已存在")
        config.tasks.append(task)
        self.save_config(config)

    def update_task(self, updated_task: TaskConfig):
        """更新一个现有任务"""
        config = self.get_config()
        for i, task in enumerate(config.tasks):
            if task.id == updated_task.id:
                config.tasks[i] = updated_task
                self.save_config(config)
                return
        raise ValueError(f"任务 ID '{updated_task.id}' 不存在")

    def delete_task(self, task_id: str):
        """删除一个任务"""
        config = self.get_config()
        initial_len = len(config.tasks)
        config.tasks = [t for t in config.tasks if t.id != task_id]
        if len(config.tasks) == initial_len:
            raise ValueError(f"任务 ID '{task_id}' 不存在")
        self.save_config(config)

# 全局配置管理器实例
config_manager = ConfigManager()