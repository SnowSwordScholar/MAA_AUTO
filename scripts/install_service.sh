#!/bin/bash

# MAA 任务调度器系统服务安装脚本

set -e

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 获取当前用户信息（从 SUDO_USER 环境变量）
if [ -z "$SUDO_USER" ]; then
    echo "错误: 无法获取用户信息，请使用 sudo 运行"
    exit 1
fi

REAL_USER="$SUDO_USER"
REAL_HOME=$(eval echo ~$REAL_USER)
PROJECT_DIR="$REAL_HOME/Task/MAA_Auto"

echo "=== MAA 任务调度器系统服务安装 ==="
echo "用户: $REAL_USER"
echo "项目目录: $PROJECT_DIR"

# 检查项目目录是否存在
if [ ! -d "$PROJECT_DIR" ]; then
    echo "错误: 项目目录不存在: $PROJECT_DIR"
    exit 1
fi

# 检查 uv 是否安装
UV_PATH=$(which uv || echo "")
if [ -z "$UV_PATH" ]; then
    # 检查用户本地安装的 uv
    if [ -f "$REAL_HOME/.local/bin/uv" ]; then
        UV_PATH="$REAL_HOME/.local/bin/uv"
    else
        echo "错误: 未找到 uv 命令"
        exit 1
    fi
fi

echo "UV 路径: $UV_PATH"

# 创建 systemd 服务文件
SERVICE_FILE="/etc/systemd/system/maa-scheduler.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=MAA Task Scheduler
Documentation=https://github.com/SnowSwordScholar/MAA_AUTO
After=network.target
Wants=network.target

[Service]
Type=exec
User=$REAL_USER
Group=$REAL_USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$REAL_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=HOME=$REAL_HOME
ExecStart=$UV_PATH run python -m src.maa_scheduler.main main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=maa-scheduler
KillMode=mixed
TimeoutStopSec=30

# 安全设置
PrivateDevices=yes
ProtectSystem=strict
ReadWritePaths=$PROJECT_DIR $REAL_HOME/.cache $REAL_HOME/.local
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
EOF

echo "已创建服务文件: $SERVICE_FILE"

# 重新加载 systemd 配置
systemctl daemon-reload

echo "已重新加载 systemd 配置"

# 设置日志轮转
LOG_ROTATE_FILE="/etc/logrotate.d/maa-scheduler"
cat > "$LOG_ROTATE_FILE" << EOF
$PROJECT_DIR/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    notifempty
    create 644 $REAL_USER $REAL_USER
    copytruncate
}
EOF

echo "已配置日志轮转: $LOG_ROTATE_FILE"

echo ""
echo "=== 安装完成 ==="
echo ""
echo "可用命令:"
echo "  启动服务:        sudo systemctl start maa-scheduler"
echo "  停止服务:        sudo systemctl stop maa-scheduler"
echo "  重启服务:        sudo systemctl restart maa-scheduler"
echo "  查看状态:        sudo systemctl status maa-scheduler"
echo "  启用开机自启:    sudo systemctl enable maa-scheduler"
echo "  禁用开机自启:    sudo systemctl disable maa-scheduler"
echo "  查看日志:        sudo journalctl -u maa-scheduler -f"
echo ""

# 询问是否启用服务
read -p "是否现在启用并启动服务？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "启用服务..."
    systemctl enable maa-scheduler
    echo "启动服务..."
    systemctl start maa-scheduler
    sleep 2
    echo "服务状态:"
    systemctl status maa-scheduler --no-pager
fi

echo ""
echo "Web 界面访问地址: http://localhost:8080"