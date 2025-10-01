"""
Web 控制界面模块
提供任务管理、监控、配置的 Web 界面
"""

import logging
import uuid
import asyncio
from typing import Dict, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import AppConfig, TaskConfig, config_manager
from .scheduler import scheduler
from .executor import task_executor
from .notification import notification_service

logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(title="MAA 任务调度器", version="0.1.0")

# 静态文件和模板
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# --- Web 页面路由 ---

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

# --- API 路由 ---

# 状态和监控
@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    return scheduler.get_scheduler_status()

@app.get("/api/resource-groups")
async def get_resource_groups():
    """获取资源分组状态"""
    return scheduler.resource_manager.get_all_groups_status()

@app.get("/api/tasks", response_model=List[Dict])
async def get_tasks_with_status():
    """获取所有任务的配置及状态"""
    tasks = config_manager.get_config().tasks
    result = []
    for task in tasks:
        status = task_executor.get_task_status(task.id)
        job = scheduler.scheduler.get_job(task.id)
        next_run_time = job.next_run_time if job else None
        
        task_dict = task.dict()
        task_dict['status'] = status.value
        task_dict['next_run_time'] = next_run_time.isoformat() if next_run_time else None
        result.append(task_dict)
    return result

@app.get("/api/tasks/{task_id}", response_model=TaskConfig)
async def get_task(task_id: str):
    """获取单个任务的配置"""
    task = config_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

@app.post("/api/tasks", status_code=201)
async def create_task(task_config: TaskConfig):
    """创建新任务"""
    try:
        # 确保为新任务生成唯一ID
        task_config.id = str(uuid.uuid4())
        config_manager.add_task(task_config)
        await scheduler.reload_tasks()
        return {"message": "任务创建成功", "task_id": task_config.id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"创建任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建任务失败: {e}")

@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, task_config: TaskConfig):
    """更新任务"""
    if task_id != task_config.id:
        raise HTTPException(status_code=400, detail="URL中的任务ID与请求体中的ID不匹配")
    try:
        config_manager.update_task(task_config)
        await scheduler.reload_tasks()
        return {"message": "任务更新成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"更新任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新任务失败: {e}")

@app.delete("/api/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str):
    """删除任务"""
    try:
        # 如果任务正在运行，先取消
        if task_id in task_executor.get_running_tasks():
            await task_executor.cancel_task(task_id)
        
        config_manager.delete_task(task_id)
        await scheduler.reload_tasks()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"删除任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除任务失败: {e}")

@app.post("/api/tasks/{task_id}/run")
async def run_task_manually(task_id: str):
    """手动执行一次任务"""
    try:
        task = config_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 手动执行任务，绕过调度器
        asyncio.create_task(scheduler._execute_and_handle_completion(task))
        return {"message": "任务已开始手动执行"}
    except Exception as e:
        logger.error(f"手动执行任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"手动执行任务失败: {e}")

@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消正在运行的任务"""
    success = await task_executor.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务未在运行中或无法取消")
    return {"message": "任务取消请求已发送"}

# 配置管理
@app.get("/api/config", response_model=AppConfig)
async def get_app_config():
    """获取当前的应用配置"""
    return config_manager.get_config()

@app.post("/api/config")
async def save_app_config(config: AppConfig):
    """保存应用配置"""
    try:
        config_manager.save_config(config)
        await scheduler.reload_tasks()
        return {"message": "配置保存成功，部分设置可能需要重启应用生效"}
    except Exception as e:
        logger.error(f"保存配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存配置失败: {e}")

# 日志和通知
@app.get("/api/logs/{task_id}")
async def get_task_logs(task_id: str, lines: int = 100):
    """获取任务的临时日志"""
    try:
        temp_log_file = task_executor.get_temp_log_file(task_id)
        if not temp_log_file or not temp_log_file.exists():
            return {"lines": [], "total_lines": 0, "message": "任务没有临时日志或日志文件不存在"}

        with open(temp_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        recent_lines = all_lines[-lines:]
        return {"lines": recent_lines, "total_lines": len(all_lines)}
    except Exception as e:
        logger.error(f"获取任务日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取任务日志失败")


@app.get("/api/tasks/{task_id}/logs/live")
async def get_live_task_logs(task_id: str, limit: int = 200):
    """获取任务的实时日志缓冲"""
    try:
        lines = task_executor.get_live_logs(task_id, limit)
        status = task_executor.get_task_status(task_id)
        return {
            "lines": lines,
            "count": len(lines),
            "status": status.value if status else None
        }
    except Exception as e:
        logger.error(f"获取实时日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取实时日志失败")

@app.get("/api/logs")
async def get_main_log(limit: int = 100):
    """获取主日志文件内容"""
    try:
        log_file = config_manager.get_config().logging.file
        log_path = Path(log_file)
        if not log_path.exists():
            return {"lines": [], "message": "主日志文件不存在"}
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            
        recent_lines = all_lines[-limit:]
        return {"lines": recent_lines}
    except Exception as e:
        logger.error(f"获取主日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取主日志失败")

@app.post("/api/test-notification")
async def test_notification():
    """发送测试通知"""
    try:
        await notification_service.send_webhook_notification(
            title="MAA调度器测试",
            content=f"这是一条来自Web界面的测试通知。",
            tag="test"
        )
        return {"message": "测试通知已发送"}
    except Exception as e:
        logger.error(f"发送测试通知失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"发送测试通知失败: {e}")

# 异常处理
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": exc.detail or "Not Found"})
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"内部服务器错误: {exc}", exc_info=True)
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    return templates.TemplateResponse("500.html", {"request": request}, status_code=500)