"""
Web 控制界面模块
提供任务管理、监控、配置的 Web 界面
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError

from .config import TaskConfig, TriggerConfig, config_manager
from .scheduler import scheduler, SchedulerMode
from .executor import task_executor, TaskStatus
from .notification import notification_service

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(title="MAA 任务调度器", version="0.1.0")

# 静态文件和模板
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# API 模型
class TaskCreateRequest(BaseModel):
    name: str
    description: str = ""
    priority: int = 5
    resource_group: str
    trigger_type: str
    
    # Cron 触发器
    cron_expression: Optional[str] = None
    
    # 间隔触发器
    interval_seconds: Optional[int] = None
    
    # 随机触发器
    random_start_time: Optional[str] = None
    random_end_time: Optional[str] = None
    
    # 模拟器任务
    is_emulator_task: bool = False
    emulator_device_id: Optional[str] = None
    target_resolution: Optional[str] = None
    startup_app: Optional[str] = None
    
    # 任务命令
    main_command: Optional[str] = None
    working_directory: Optional[str] = None
    
    # 日志配置
    enable_global_log: bool = True
    enable_temp_log: bool = False
    
    # 通知配置
    notify_on_success: bool = False
    notify_on_failure: bool = True
    success_message: str = ""
    failure_message: str = ""

class SchedulerModeRequest(BaseModel):
    mode: str

# Web 路由
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    """任务管理页面"""
    return templates.TemplateResponse("tasks.html", {"request": request})

@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page(request: Request):
    """监控页面"""
    return templates.TemplateResponse("monitor.html", {"request": request})

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """日志页面"""
    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """设置页面"""
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """设置页面"""
    return templates.TemplateResponse("settings.html", {"request": request})

# API 路由
@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    return scheduler.get_scheduler_status()

@app.get("/api/tasks")
async def get_tasks():
    """获取任务列表"""
    return scheduler.get_task_list()

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    task = config_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    status = task_executor.get_task_status(task_id)
    result = task_executor.get_task_result(task_id)
    
    return {
        "task": task.dict(),
        "status": status.value,
        "result": result.__dict__ if result else None
    }

@app.post("/api/tasks")
async def create_task(task_request: TaskCreateRequest):
    """创建任务"""
    try:
        # 生成任务 ID
        import uuid
        task_id = str(uuid.uuid4())
        
        # 创建触发器配置
        trigger = TriggerConfig(
            trigger_type=task_request.trigger_type,
            cron_expression=task_request.cron_expression,
            interval_seconds=task_request.interval_seconds,
            random_start_time=task_request.random_start_time,
            random_end_time=task_request.random_end_time
        )
        
        # 创建任务配置
        task_config = TaskConfig(
            id=task_id,
            name=task_request.name,
            description=task_request.description,
            priority=task_request.priority,
            resource_group=task_request.resource_group,
            trigger=trigger,
            is_emulator_task=task_request.is_emulator_task,
            emulator_device_id=task_request.emulator_device_id,
            target_resolution=task_request.target_resolution,
            startup_app=task_request.startup_app,
            main_command=task_request.main_command or "maa",
            working_directory=task_request.working_directory,
            enable_global_log=task_request.enable_global_log,
            enable_temp_log=task_request.enable_temp_log,
            notify_on_success=task_request.notify_on_success,
            notify_on_failure=task_request.notify_on_failure,
            success_message=task_request.success_message,
            failure_message=task_request.failure_message
        )
        
        # 保存任务
        config_manager.add_task(task_config)
        
        # 重新加载调度器任务
        await scheduler.reload_tasks()
        
        return {"message": "任务创建成功", "task_id": task_id}
    
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"参数验证失败: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建任务失败")

@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, task_request: TaskCreateRequest):
    """更新任务"""
    try:
        # 检查任务是否存在
        existing_task = config_manager.get_task(task_id)
        if not existing_task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 创建新的任务配置
        trigger = TriggerConfig(
            trigger_type=task_request.trigger_type,
            cron_expression=task_request.cron_expression,
            interval_seconds=task_request.interval_seconds,
            random_start_time=task_request.random_start_time,
            random_end_time=task_request.random_end_time
        )
        
        task_config = TaskConfig(
            id=task_id,
            name=task_request.name,
            description=task_request.description,
            priority=task_request.priority,
            resource_group=task_request.resource_group,
            trigger=trigger,
            is_emulator_task=task_request.is_emulator_task,
            emulator_device_id=task_request.emulator_device_id,
            target_resolution=task_request.target_resolution,
            startup_app=task_request.startup_app,
            main_command=task_request.main_command or "maa",
            working_directory=task_request.working_directory,
            enable_global_log=task_request.enable_global_log,
            enable_temp_log=task_request.enable_temp_log,
            notify_on_success=task_request.notify_on_success,
            notify_on_failure=task_request.notify_on_failure,
            success_message=task_request.success_message,
            failure_message=task_request.failure_message
        )
        
        # 更新任务
        config_manager.update_task(task_config)
        
        # 重新加载调度器任务
        await scheduler.reload_tasks()
        
        return {"message": "任务更新成功"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新任务失败")

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    try:
        # 检查任务是否存在
        if not config_manager.get_task(task_id):
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 如果任务正在运行，先取消
        if task_id in task_executor.get_running_tasks():
            await task_executor.cancel_task(task_id)
        
        # 删除任务
        config_manager.delete_task(task_id)
        
        # 重新加载调度器任务
        await scheduler.reload_tasks()
        
        return {"message": "任务删除成功"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除任务失败")

@app.post("/api/tasks/{task_id}/run")
async def run_task(task_id: str):
    """手动执行任务"""
    try:
        if scheduler.mode != SchedulerMode.SINGLE_TASK:
            raise HTTPException(status_code=400, detail="必须在单任务模式下才能手动执行任务")
        
        execution_id = await scheduler.execute_single_task(task_id)
        return {"message": "任务开始执行", "execution_id": execution_id}
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"执行任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="执行任务失败")

@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    try:
        success = await task_executor.cancel_task(task_id)
        if success:
            return {"message": "任务已取消"}
        else:
            raise HTTPException(status_code=404, detail="任务未在运行中")
    
    except Exception as e:
        logger.error(f"取消任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="取消任务失败")

@app.post("/api/scheduler/mode")
async def set_scheduler_mode(request: SchedulerModeRequest):
    """设置调度器模式"""
    try:
        if request.mode == "scheduler":
            scheduler.set_mode(SchedulerMode.SCHEDULER)
        elif request.mode == "single_task":
            scheduler.set_mode(SchedulerMode.SINGLE_TASK)
        else:
            raise HTTPException(status_code=400, detail="无效的模式")
        
        return {"message": f"调度器模式已设置为: {request.mode}"}
    
    except Exception as e:
        logger.error(f"设置调度器模式失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="设置调度器模式失败")

@app.post("/api/scheduler/start")
async def start_scheduler():
    """启动调度器"""
    try:
        await scheduler.start()
        return {"message": "调度器已启动"}
    
    except Exception as e:
        logger.error(f"启动调度器失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="启动调度器失败")

@app.post("/api/scheduler/stop")
async def stop_scheduler():
    """停止调度器"""
    try:
        await scheduler.stop()
        return {"message": "调度器已停止"}
    
    except Exception as e:
        logger.error(f"停止调度器失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="停止调度器失败")

@app.get("/api/resource-groups")
async def get_resource_groups():
    """获取资源分组"""
    return scheduler.resource_manager.get_all_groups_status()

@app.get("/api/logs/{task_id}")
async def get_task_logs(task_id: str, lines: int = 100):
    """获取任务日志"""
    try:
        # 获取临时日志文件路径
        temp_log_file = task_executor.get_temp_log_file(task_id)
        
        if temp_log_file and Path(temp_log_file).exists():
            with open(temp_log_file, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
                
            # 返回最后 N 行
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            return {
                "task_id": task_id,
                "lines": recent_lines,
                "total_lines": len(all_lines)
            }
        else:
            # 如果没有临时日志文件，返回执行结果中的输出
            result = task_executor.get_task_result(task_id)
            if result:
                lines_list = []
                if result.stdout:
                    lines_list.extend(result.stdout.split('\n'))
                if result.stderr:
                    lines_list.extend(result.stderr.split('\n'))
                
                return {
                    "task_id": task_id,
                    "lines": lines_list,
                    "total_lines": len(lines_list)
                }
            else:
                return {
                    "task_id": task_id,
                    "lines": [],
                    "total_lines": 0
                }
    
    except Exception as e:
        logger.error(f"获取任务日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取任务日志失败")

@app.post("/api/test-notification")
async def test_notification():
    """发送测试通知"""
    try:
        await notification_service.send_webhook_notification(
            "test_notification", 
            "这是一条测试通知", 
            {"timestamp": datetime.now().isoformat(), "source": "web_ui"}
        )
        return {"message": "测试通知已发送"}
    except Exception as e:
        logger.error(f"发送测试通知失败: {e}")
        raise HTTPException(status_code=500, detail="发送测试通知失败")


@app.get("/api/config")
async def get_config():
    """获取当前配置"""
    try:
        # 返回安全的配置信息（不包含敏感数据）
        safe_config = {
            "app_name": "MAA Scheduler",
            "version": "0.1.0",
            "debug": False,
            "web_host": "127.0.0.1",
            "web_port": 8080,
            "scheduler_enabled": scheduler.is_running,
            "max_workers": 4,
            "task_timeout": 3600,
            "log_level": "INFO",
            "log_file": "logs/maa_scheduler.log",
            "log_max_size": "10MB",
            "log_backup_count": 5,
            "webhook": {
                "uid": os.getenv('WEBHOOK_UID', ''),
                "base_url": os.getenv('WEBHOOK_BASE_URL', '')
            }
        }
        return safe_config
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail="获取配置失败")


@app.post("/api/config")
async def update_config(config_data: dict):
    """更新配置（预留接口）"""
    try:
        # 这里可以实现配置更新逻辑
        # 目前只是演示，实际需要根据具体需求实现
        logger.info(f"配置更新请求: {config_data}")
        return {"message": "配置更新功能开发中"}
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail="更新配置失败")


@app.get("/api/logs")
async def get_logs(limit: int = 100, offset: int = 0, level: str = None):
    """获取系统日志"""
    try:
        # 这里返回模拟的日志数据
        # 实际项目中可以从日志文件或数据库读取
        sample_logs = [
            {
                "timestamp": "2025-09-30T01:20:00Z",
                "level": "INFO",
                "message": "调度器启动成功",
                "source": "scheduler"
            },
            {
                "timestamp": "2025-09-30T01:19:30Z", 
                "level": "INFO",
                "message": "Web服务启动",
                "source": "web_ui"
            },
            {
                "timestamp": "2025-09-30T01:19:00Z",
                "level": "INFO", 
                "message": "配置加载完成",
                "source": "config"
            }
        ]
        
        # 应用过滤器
        filtered_logs = sample_logs
        if level:
            filtered_logs = [log for log in filtered_logs if log["level"].lower() == level.lower()]
        
        # 应用分页
        paginated_logs = filtered_logs[offset:offset + limit]
        
        return {
            "logs": paginated_logs,
            "total": len(filtered_logs),
            "offset": offset,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"获取日志失败: {e}")
        raise HTTPException(status_code=500, detail="获取日志失败")

@app.get("/api/config")
async def get_config():
    """获取应用配置"""
    return config_manager.load_app_config().dict()

# 异常处理
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"内部服务器错误: {exc}", exc_info=True)
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    return templates.TemplateResponse("500.html", {"request": request}, status_code=500)