"""
通知系统模块
处理 Webhook 推送通知
"""

import aiohttp
import logging
from typing import Optional

from .config import config_manager, TaskConfig

logger = logging.getLogger(__name__)

class NotificationService:
    """通知服务"""
    
    def __init__(self):
        self._webhook_config = None

    def _load_config(self):
        if not self._webhook_config:
            self._webhook_config = config_manager.get_config().webhook
        return self._webhook_config

    async def send_webhook_notification(
        self,
        title: str,
        content: str,
        tag: Optional[str] = "MAA"
    ) -> bool:
        """发送 Webhook 通知"""
        webhook_config = self._load_config()
        if not webhook_config:
            logger.debug("Webhook 配置未设置，跳过通知发送")
            return False
        
        # 使用 ServerChan 的 URL 格式
        url = f"{webhook_config.base_url}/{webhook_config.token}.send"
        
        # ServerChan 使用 POST 请求和 form-data
        data = {
            'title': title,
            'desp': content,
            'channel': tag # ServerChan 的 'channel' 类似于 'tag'
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        resp_json = await response.json()
                        if resp_json.get("code") == 0:
                            logger.info(f"通知发送成功: {title}")
                            return True
                        else:
                            logger.error(f"通知发送失败，API返回错误: {resp_json.get('message')}")
                            return False
                    else:
                        logger.error(f"通知发送失败，HTTP状态码: {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"通知发送异常: {e}", exc_info=True)
            return False

    async def notify_task_status(self, task_config: TaskConfig, status: str):
        """任务状态通用通知"""
        title = f"任务 {status}: {task_config.name}"
        content = f"任务 '{task_config.name}' (ID: {task_config.id}) 已{status}。"
        tag = f"task-{status.lower()}"
        await self.send_webhook_notification(title, content, tag)

    async def notify_scheduler_status(self, status: str, message: str = ""):
        """调度器状态通知"""
        title = f"调度器状态: {status}"
        content = f"调度器已 {status}。"
        if message:
            content += f"""

{message}"""
        await self.send_webhook_notification(title, content, "scheduler-status")

    async def notify_system_error(self, error_type: str, error_message: str, category: str = "system-error"):
        """系统错误通知"""
        title = f"系统错误: {error_type}"
        content = f"""系统发生严重错误。

**分类**: {category}
**类型**: {error_type}
**信息**: {error_message}"""
        await self.send_webhook_notification(title, content, category or "system-error")

# 全局通知服务实例
notification_service = NotificationService()