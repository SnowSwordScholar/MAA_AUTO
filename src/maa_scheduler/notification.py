"""
通知系统模块
处理 Webhook 推送通知
"""

import asyncio
import aiohttp
from typing import Optional, Dict, Any
from urllib.parse import urlencode
import logging

from .config import config_manager

logger = logging.getLogger(__name__)

class NotificationService:
    """通知服务"""
    
    def __init__(self):
        self.webhook_config = config_manager.load_webhook_config()
    
    async def send_webhook_notification(
        self,
        title: str,
        message: str,
        tags: str = "MAA",
        **kwargs
    ) -> bool:
        """发送 Webhook 通知"""
        if not self.webhook_config:
            logger.warning("Webhook 配置未设置，跳过通知发送")
            return False
        
        try:
            # 构建请求参数
            params = {
                'title': title,
                'desp': message,
                'tags': tags
            }
            
            # 添加额外参数
            params.update(kwargs)
            
            # 构建完整 URL
            url = f"{self.webhook_config.base_url}?{urlencode(params)}"
            
            # 发送请求
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.info(f"通知发送成功: {title}")
                        return True
                    else:
                        logger.error(f"通知发送失败，状态码: {response.status}")
                        return False
        
        except asyncio.TimeoutError:
            logger.error("通知发送超时")
            return False
        except Exception as e:
            logger.error(f"通知发送异常: {e}")
            return False
    
    async def notify_task_started(self, task_name: str, task_id: str):
        """任务开始通知"""
        title = f"任务开始 - {task_name}"
        message = f"任务 {task_name} (ID: {task_id}) 开始执行"
        await self.send_webhook_notification(title, message, tags="任务,开始")
    
    async def notify_task_completed(self, task_name: str, task_id: str, success: bool, message: str = ""):
        """任务完成通知"""
        status = "成功" if success else "失败"
        title = f"任务{status} - {task_name}"
        
        if message:
            full_message = f"任务 {task_name} (ID: {task_id}) 执行{status}\n\n详情: {message}"
        else:
            full_message = f"任务 {task_name} (ID: {task_id}) 执行{status}"
        
        tags = f"任务,{status}"
        await self.send_webhook_notification(title, full_message, tags=tags)
    
    async def notify_keyword_matched(self, task_name: str, task_id: str, keywords: list, message: str = ""):
        """关键词匹配通知"""
        title = f"关键词触发 - {task_name}"
        keywords_str = ", ".join(keywords)
        
        if message:
            full_message = f"任务 {task_name} (ID: {task_id}) 日志中发现关键词: {keywords_str}\n\n详情: {message}"
        else:
            full_message = f"任务 {task_name} (ID: {task_id}) 日志中发现关键词: {keywords_str}"
        
        await self.send_webhook_notification(title, full_message, tags="关键词,监控")
    
    async def notify_scheduler_status(self, status: str, message: str = ""):
        """调度器状态通知"""
        title = f"调度器状态 - {status}"
        
        if message:
            full_message = f"调度器状态变更: {status}\n\n详情: {message}"
        else:
            full_message = f"调度器状态变更: {status}"
        
        await self.send_webhook_notification(title, full_message, tags="调度器,状态")
    
    async def notify_system_error(self, error_type: str, error_message: str):
        """系统错误通知"""
        title = f"系统错误 - {error_type}"
        full_message = f"系统发生错误\n\n错误类型: {error_type}\n错误信息: {error_message}"
        
        await self.send_webhook_notification(title, full_message, tags="错误,系统")

# 全局通知服务实例
notification_service = NotificationService()