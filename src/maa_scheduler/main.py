"""
MAA 任务调度器主程序
提供命令行界面和 Web 服务
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path

import uvicorn

# 添加项目根目录到sys.path以支持绝对导入
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.maa_scheduler.config import config_manager
from src.maa_scheduler.scheduler import scheduler
from src.maa_scheduler.web_ui import app
from src.maa_scheduler.notification import notification_service

# 设置日志
def setup_logging():
    """设置日志系统"""
    config = config_manager.load_app_config()
    
    # 创建日志目录
    log_file_path = Path(config.log_file)
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 配置日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 配置根日志器
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format=log_format,
        handlers=[
            logging.FileHandler(config.log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    return logging.getLogger(__name__)

logger = setup_logging()

class SchedulerApplication:
    """调度器应用主类"""
    
    def __init__(self):
        self.config = config_manager.load_app_config()
        self._shutdown_event = asyncio.Event()
    
    async def start_scheduler_only(self):
        """仅启动调度器（无Web界面）"""
        logger.info("启动MAA任务调度器（仅调度器模式）")
        
        try:
            # 启动调度器
            await scheduler.start()
            
            # 发送启动通知
            await notification_service.notify_scheduler_status(
                "已启动", 
                "MAA任务调度器已启动（仅调度器模式）"
            )
            
            logger.info("调度器启动完成，按 Ctrl+C 停止")
            
            # 等待关闭信号
            await self._shutdown_event.wait()
            
        except KeyboardInterrupt:
            logger.info("收到中断信号，准备关闭...")
        except Exception as e:
            logger.error(f"调度器运行异常: {e}", exc_info=True)
            await notification_service.notify_system_error("调度器异常", str(e))
        finally:
            await self._shutdown()
    
    async def start_web_only(self, host: str = None, port: int = None):
        """仅启动Web界面（无调度器）"""
        host = host or self.config.web_host
        port = port or self.config.web_port
        
        logger.info(f"启动MAA任务调度器Web界面: http://{host}:{port}")
        
        try:
            # 配置uvicorn
            config = uvicorn.Config(
                app=app,
                host=host,
                port=port,
                log_level=self.config.log_level.lower(),
                access_log=True
            )
            
            server = uvicorn.Server(config)
            
            # 启动Web服务
            await server.serve()
            
        except Exception as e:
            logger.error(f"Web服务异常: {e}", exc_info=True)
            raise
    
    async def start_full(self, host: str = None, port: int = None):
        """启动完整服务（调度器 + Web界面）"""
        host = host or self.config.web_host
        port = port or self.config.web_port
        
        logger.info(f"启动MAA任务调度器完整服务: http://{host}:{port}")
        
        try:
            # 启动调度器
            await scheduler.start()
            
            # 发送启动通知
            await notification_service.notify_scheduler_status(
                "已启动",
                f"MAA任务调度器已启动\nWeb界面: http://{host}:{port}"
            )
            
            # 配置uvicorn
            config = uvicorn.Config(
                app=app,
                host=host,
                port=port,
                log_level=self.config.log_level.lower(),
                access_log=True
            )
            
            server = uvicorn.Server(config)
            
            # 启动Web服务
            await server.serve()
            
        except KeyboardInterrupt:
            logger.info("收到中断信号，准备关闭...")
        except Exception as e:
            logger.error(f"服务运行异常: {e}", exc_info=True)
            await notification_service.notify_system_error("服务异常", str(e))
        finally:
            await self._shutdown()
    
    async def _shutdown(self):
        """关闭服务"""
        logger.info("正在关闭调度器...")
        
        try:
            # 停止调度器
            await scheduler.stop()
            
            # 发送停止通知
            await notification_service.notify_scheduler_status(
                "已停止",
                "MAA任务调度器已停止"
            )
            
            logger.info("调度器已安全关闭")
            
        except Exception as e:
            logger.error(f"关闭服务异常: {e}", exc_info=True)
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，准备关闭...")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

async def check_config():
    """检查配置"""
    print("=== MAA 任务调度器配置检查 ===\n")
    
    # 检查基础配置
    config = config_manager.load_app_config()
    print(f"应用名称: {config.app_name}")
    print(f"版本: {config.version}")
    print(f"调试模式: {config.debug}")
    print(f"Web服务: {config.web_host}:{config.web_port}")
    print(f"最大工作线程: {config.max_workers}")
    print(f"任务超时: {config.task_timeout}秒")
    print(f"日志级别: {config.log_level}")
    print(f"日志文件: {config.log_file}")
    
    # 检查Webhook配置
    if config.webhook:
        print(f"\nWebhook配置:")
        print(f"  UID: {config.webhook.uid}")
        print(f"  令牌: {config.webhook.token[:10]}...")
        print(f"  URL: {config.webhook.base_url}")
    else:
        print("\n⚠️  警告: 未配置Webhook通知")
    
    # 检查资源分组
    print(f"\n资源分组配置:")
    for group in config.resource_groups:
        print(f"  - {group.name}: {group.description} (最大并发: {group.max_concurrent})")
    
    # 检查任务配置
    tasks = config_manager.load_tasks_config()
    print(f"\n任务配置:")
    print(f"  总任务数: {len(tasks)}")
    enabled_tasks = [task for task in tasks if task.enabled]
    print(f"  启用任务: {len(enabled_tasks)}")
    
    if tasks:
        print("  任务列表:")
        for task in tasks:
            status = "✓" if task.enabled else "✗"
            print(f"    {status} {task.name} ({task.trigger.trigger_type}) - {task.resource_group}")
    
    print("\n=== 配置检查完成 ===")

async def list_tasks():
    """列出所有任务"""
    print("=== 任务列表 ===\n")
    
    tasks = config_manager.load_tasks_config()
    
    if not tasks:
        print("暂无任务")
        return
    
    for i, task in enumerate(tasks, 1):
        status = "✓ 启用" if task.enabled else "✗ 禁用"
        print(f"{i}. {task.name}")
        print(f"   ID: {task.id}")
        print(f"   状态: {status}")
        print(f"   优先级: {task.priority}")
        print(f"   资源分组: {task.resource_group}")
        print(f"   触发类型: {task.trigger.trigger_type}")
        print(f"   执行命令: {task.main_command}")
        if task.description:
            print(f"   描述: {task.description}")
        print()

async def test_notification():
    """测试通知功能"""
    print("正在发送测试通知...")
    
    try:
        await notification_service.send_webhook_notification(
            "MAA调度器测试",
            f"这是一条测试通知，发送时间: {asyncio.get_event_loop().time()}",
            "测试"
        )
        print("✓ 测试通知发送成功")
    except Exception as e:
        print(f"✗ 测试通知发送失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MAA 任务调度器")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 启动命令
    start_parser = subparsers.add_parser('start', help='启动调度器（无Web界面）')
    
    # Web界面命令
    web_parser = subparsers.add_parser('web', help='启动Web界面（无调度器）')
    web_parser.add_argument('--host', default=None, help='Web服务主机地址')
    web_parser.add_argument('--port', type=int, default=None, help='Web服务端口')
    
    # 完整服务命令
    main_parser = subparsers.add_parser('main', help='启动完整服务（调度器+Web界面）')
    main_parser.add_argument('--host', default=None, help='Web服务主机地址')
    main_parser.add_argument('--port', type=int, default=None, help='Web服务端口')
    main_parser.add_argument('--web-only', action='store_true', help='仅启动Web界面')
    
    # 工具命令
    subparsers.add_parser('check-config', help='检查配置')
    subparsers.add_parser('list-tasks', help='列出所有任务')
    
    # 测试命令
    test_parser = subparsers.add_parser('test', help='测试功能')
    test_subparsers = test_parser.add_subparsers(dest='test_command')
    test_subparsers.add_parser('notification', help='测试通知功能')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    # 创建应用实例
    app_instance = SchedulerApplication()
    
    try:
        if args.command == 'check-config':
            asyncio.run(check_config())
        elif args.command == 'list-tasks':
            asyncio.run(list_tasks())
        elif args.command == 'test':
            if args.test_command == 'notification':
                asyncio.run(test_notification())
            else:
                print("未知的测试命令")
        elif args.command == 'start':
            app_instance.setup_signal_handlers()
            asyncio.run(app_instance.start_scheduler_only())
        elif args.command == 'web':
            asyncio.run(app_instance.start_web_only(args.host, args.port))
        elif args.command == 'main':
            if args.web_only:
                asyncio.run(app_instance.start_web_only(args.host, args.port))
            else:
                app_instance.setup_signal_handlers()
                asyncio.run(app_instance.start_full(args.host, args.port))
        else:
            print(f"未知命令: {args.command}")
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()