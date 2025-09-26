#!/bin/bash
# MAA任务调度器启动脚本
# 同时启动调度器和Web界面

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 日志文件
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

SCHEDULER_LOG="$LOG_DIR/scheduler.log"
WEB_LOG="$LOG_DIR/web.log"

echo "=== MAA任务调度器启动 $(date) ===" | tee -a "$SCHEDULER_LOG" "$WEB_LOG"

# 启动调度器（后台）
echo "启动任务调度器..." | tee -a "$SCHEDULER_LOG"
nohup uv run python main.py run --config task_config.ini >> "$SCHEDULER_LOG" 2>&1 &
SCHEDULER_PID=$!
echo "调度器PID: $SCHEDULER_PID" | tee -a "$SCHEDULER_LOG"

# 等待一秒让调度器启动
sleep 1

# 启动Web界面（后台）
echo "启动Web管理界面..." | tee -a "$WEB_LOG"
nohup uv run python src/maa_scheduler/web/app.py --config task_config.ini >> "$WEB_LOG" 2>&1 &
WEB_PID=$!
echo "Web界面PID: $WEB_PID" | tee -a "$WEB_LOG"

# 保存PID文件
echo "$SCHEDULER_PID" > "$SCRIPT_DIR/scheduler.pid"
echo "$WEB_PID" > "$SCRIPT_DIR/web.pid"

echo "所有服务已启动："
echo "  - 调度器: PID $SCHEDULER_PID"
echo "  - Web界面: PID $WEB_PID (http://localhost:5000)"
echo "  - 日志: $LOG_DIR/"

# 监控进程
while true; do
    if ! kill -0 "$SCHEDULER_PID" 2>/dev/null; then
        echo "$(date): 调度器进程异常退出，重新启动..." | tee -a "$SCHEDULER_LOG"
        nohup uv run python main.py run --config task_config.ini >> "$SCHEDULER_LOG" 2>&1 &
        SCHEDULER_PID=$!
        echo "$SCHEDULER_PID" > "$SCRIPT_DIR/scheduler.pid"
    fi
    
    if ! kill -0 "$WEB_PID" 2>/dev/null; then
        echo "$(date): Web界面进程异常退出，重新启动..." | tee -a "$WEB_LOG"
        nohup uv run python src/maa_scheduler/web/app.py --config task_config.ini >> "$WEB_LOG" 2>&1 &
        WEB_PID=$!
        echo "$WEB_PID" > "$SCRIPT_DIR/web.pid"
    fi
    
    sleep 10
done