"""系统监控指标采集模块"""

from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psutil

APP_START_TIME = datetime.now(timezone.utc)
_PROCESS = psutil.Process(os.getpid())
_PROCESS.cpu_percent(interval=None)

_BYTE_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]


def _format_bytes(value: float) -> str:
    """将字节值转换成人类可读格式"""
    step = 1024.0
    idx = 0
    output = float(value)
    while output >= step and idx < len(_BYTE_UNITS) - 1:
        output /= step
        idx += 1
    return f"{output:.1f} {_BYTE_UNITS[idx]}"


def _get_cpu_metrics() -> Dict[str, Any]:
    per_cpu: List[float] = psutil.cpu_percent(interval=0.1, percpu=True)
    if per_cpu:
        overall = sum(per_cpu) / len(per_cpu)
    else:
        overall = psutil.cpu_percent(interval=None)
        per_cpu = [overall]

    load_average: Optional[List[float]] = None
    try:
        load_average = list(psutil.getloadavg())  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        load_average = None

    frequency = None
    try:
        freq = psutil.cpu_freq()
        if freq:
            frequency = {
                "current": freq.current,
                "min": freq.min,
                "max": freq.max,
            }
    except Exception:
        frequency = None

    return {
        "percent": overall,
        "per_cpu": per_cpu,
        "cores": psutil.cpu_count(logical=True) or len(per_cpu),
        "physical_cores": psutil.cpu_count(logical=False),
        "load_average": load_average,
        "frequency": frequency,
    }


def _get_memory_metrics() -> Dict[str, Any]:
    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "virtual": {
            "total": virtual.total,
            "available": virtual.available,
            "used": virtual.used,
            "free": virtual.free,
            "percent": virtual.percent,
            "human": {
                "total": _format_bytes(virtual.total),
                "available": _format_bytes(virtual.available),
                "used": _format_bytes(virtual.used),
                "free": _format_bytes(virtual.free),
            },
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "free": swap.free,
            "percent": swap.percent,
            "human": {
                "total": _format_bytes(swap.total) if swap.total else "0 B",
                "used": _format_bytes(swap.used) if swap.total else "0 B",
                "free": _format_bytes(swap.free) if swap.total else "0 B",
            },
        },
    }


def _get_disk_metrics() -> Dict[str, Any]:
    try:
        disk_usage = psutil.disk_usage('/')
        return {
            "total": disk_usage.total,
            "used": disk_usage.used,
            "free": disk_usage.free,
            "percent": disk_usage.percent,
            "human": {
                "total": _format_bytes(disk_usage.total),
                "used": _format_bytes(disk_usage.used),
                "free": _format_bytes(disk_usage.free),
            },
        }
    except Exception:
        return {}


def _get_process_metrics() -> Dict[str, Any]:
    with _PROCESS.oneshot():
        try:
            cpu_percent = _PROCESS.cpu_percent(interval=None)
        except Exception:
            cpu_percent = None
        try:
            memory_info = _PROCESS.memory_full_info()
        except psutil.AccessDenied:
            memory_info = _PROCESS.memory_info()
        except Exception:
            memory_info = None

        mem = {
            "rss": getattr(memory_info, "rss", None),
            "vms": getattr(memory_info, "vms", None),
            "uss": getattr(memory_info, "uss", None),
        } if memory_info else {}

        for key, value in list(mem.items()):
            if value is None:
                mem.pop(key)
            else:
                mem[f"{key}_human"] = _format_bytes(value)

    return {
        "pid": _PROCESS.pid,
        "name": _PROCESS.name(),
        "cpu_percent": cpu_percent,
        "memory": mem,
        "threads": _PROCESS.num_threads(),
    }


def get_system_metrics() -> Dict[str, Any]:
    """获取系统指标快照"""
    now = datetime.now(timezone.utc)
    cpu = _get_cpu_metrics()
    memory = _get_memory_metrics()
    disk = _get_disk_metrics()
    process = _get_process_metrics()
    uptime_seconds = time.time() - psutil.boot_time()
    app_uptime_seconds = (now - APP_START_TIME).total_seconds()

    return {
        "timestamp": now.isoformat(),
        "cpu": cpu,
        "memory": memory,
        "disk": disk,
        "process": process,
        "uptime_seconds": uptime_seconds,
        "app_uptime_seconds": app_uptime_seconds,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        },
    }