"""
MAA任务调度器 - 通用任务流程调度系统
"""

from .core import (
    ConfigManager,
    TaskExecutor,
    ADBExecutor,
    CommandExecutor,
    HttpExecutor,
    FileExecutor,
    TaskScheduler,
    TaskType,
    TaskSchedule,
    TaskDefinition
)

__all__ = [
    'ConfigManager',
    'TaskExecutor',
    'ADBExecutor',
    'CommandExecutor',
    'HttpExecutor',
    'FileExecutor',
    'TaskScheduler',
    'TaskType',
    'TaskSchedule',
    'TaskDefinition'
]

__version__ = "1.0.0"

__version__ = "2.0.0"
__author__ = "MAA Scheduler Team"