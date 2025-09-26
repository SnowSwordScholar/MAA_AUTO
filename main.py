#!/usr/bin/env python3
"""
MAA任务调度器主入口文件 - 新版本
"""

import sys
import argparse
import signal
from pathlib import Path

# 确保可以导入本地模块
sys.path.insert(0, str(Path(__file__).parent))

from src.maa_scheduler.core.scheduler_new import TaskScheduler

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='MAA任务调度器 (新版本)')
    parser.add_argument('--config', '-c', 
                       default='task_config.ini',
                       help='配置文件路径 (默认: task_config.ini)')
    parser.add_argument('--daemon', '-d', 
                       action='store_true',
                       help='以守护进程模式运行')
    parser.add_argument('--version', '-v', 
                       action='version',
                       version='%(prog)s 2.0.0')
    
    # 添加子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 运行命令
    run_parser = subparsers.add_parser('run', help='运行调度器')
    run_parser.add_argument('--config', '-c', 
                           default='task_config.ini',
                           help='配置文件路径')
    
    # 状态命令
    status_parser = subparsers.add_parser('status', help='查看任务状态')
    status_parser.add_argument('--config', '-c', 
                              default='task_config.ini',
                              help='配置文件路径')
    
    # 列出任务命令
    list_parser = subparsers.add_parser('list', help='列出所有任务')
    list_parser.add_argument('--config', '-c', 
                            default='task_config.ini',
                            help='配置文件路径')
    
    # 测试命令
    test_parser = subparsers.add_parser('test', help='测试配置文件')
    test_parser.add_argument('--config', '-c', 
                            default='task_config.ini',
                            help='配置文件路径')
    
    args = parser.parse_args()
    
    # 如果没有指定命令，默认运行
    if not args.command:
        args.command = 'run'
    
    try:
        if args.command == 'run':
            scheduler = TaskScheduler(args.config)
            
            if args.daemon:
                # 守护进程模式
                try:
                    import daemon
                    with daemon.DaemonContext():
                        scheduler.main_loop()
                except ImportError:
                    print("守护进程模式需要python-daemon包，使用前台运行模式")
                    scheduler.main_loop()
            else:
                # 前台运行
                try:
                    scheduler.main_loop()
                except KeyboardInterrupt:
                    print("\n收到中断信号，正在停止...")
                    scheduler.running = False
                    
        elif args.command == 'status':
            scheduler = TaskScheduler(args.config)
            status = scheduler.get_task_status()
            
            print(f"任务总数: {status['total_tasks']}")
            print(f"运行中任务: {status['active_tasks']}")
            print(f"任务列表: {', '.join(status['task_list'])}")
            if status['active_task_list']:
                print(f"运行中: {', '.join(status['active_task_list'])}")
            print(f"队列组: {', '.join(status['queue_groups'])}")
            
        elif args.command == 'list':
            scheduler = TaskScheduler(args.config)
            status = scheduler.get_task_status()
            
            print("所有任务:")
            for task_name in status['task_list']:
                is_active = task_name in status['active_task_list']
                status_str = "运行中" if is_active else "空闲"
                flow = scheduler.flows.get(task_name)
                if flow:
                    print(f"  - {task_name} ({status_str}) - {flow.task_type.value}|{flow.time_params}|优先级:{flow.priority}")
                else:
                    print(f"  - {task_name} ({status_str})")
                    
        elif args.command == 'test':
            try:
                scheduler = TaskScheduler(args.config)
                print("✅ 配置文件格式正确")
                
                flows = scheduler.config.get_task_flows()
                payloads = scheduler.config.get_task_payloads()
                keywords = scheduler.config.get_task_keywords()
                templates = scheduler.config.get_webhook_templates()
                
                print(f"📋 任务流程: {len(flows)} 个")
                print(f"💼 任务负载: {len(payloads)} 个")
                print(f"🔍 关键词配置: {len(keywords)} 个")
                print(f"📨 WebHook模板: {len(templates)} 个")
                
                # 检查配置一致性
                flow_names = set(flows.keys())
                payload_names = set(payloads.keys())
                keyword_names = set(keywords.keys())
                
                if flow_names != payload_names:
                    missing_payloads = flow_names - payload_names
                    extra_payloads = payload_names - flow_names
                    if missing_payloads:
                        print(f"⚠️  缺少负载定义的任务: {', '.join(missing_payloads)}")
                    if extra_payloads:
                        print(f"⚠️  没有流程定义的负载: {', '.join(extra_payloads)}")
                else:
                    print("✅ 任务流程和负载配置一致")
                    
            except Exception as e:
                print(f"❌ 配置文件测试失败: {e}")
                sys.exit(1)
            
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()