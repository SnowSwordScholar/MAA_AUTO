#!/bin/bash
# MAA任务调度器停止脚本

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 停止MAA任务调度器 $(date) ==="

# 停止进程
if [ -f "scheduler.pid" ]; then
    SCHEDULER_PID=$(cat scheduler.pid)
    if kill -0 "$SCHEDULER_PID" 2>/dev/null; then
        echo "停止调度器进程 (PID: $SCHEDULER_PID)..."
        kill "$SCHEDULER_PID"
        sleep 2
        if kill -0 "$SCHEDULER_PID" 2>/dev/null; then
            echo "强制停止调度器进程..."
            kill -9 "$SCHEDULER_PID"
        fi
    fi
    rm -f scheduler.pid
fi

if [ -f "web.pid" ]; then
    WEB_PID=$(cat web.pid)
    if kill -0 "$WEB_PID" 2>/dev/null; then
        echo "停止Web界面进程 (PID: $WEB_PID)..."
        kill "$WEB_PID"
        sleep 2
        if kill -0 "$WEB_PID" 2>/dev/null; then
            echo "强制停止Web界面进程..."
            kill -9 "$WEB_PID"
        fi
    fi
    rm -f web.pid
fi

# 清理其他可能的Python进程
echo "清理相关进程..."
pkill -f "main.py run" 2>/dev/null || true
pkill -f "maa_scheduler/web/app.py" 2>/dev/null || true

echo "所有服务已停止"