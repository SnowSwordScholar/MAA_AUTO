#!/bin/bash

# MAA 任务调度器开发启动脚本

set -e

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== MAA 任务调度器开发环境 ==="
echo "项目目录: $PROJECT_DIR"

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "错误: uv 未安装，请先安装 uv"
    echo "安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 检查 Python 版本
echo "检查 Python 环境..."
python3 --version

# 安装依赖
echo "安装项目依赖..."
uv sync

# 创建必要的目录
echo "创建必要目录..."
mkdir -p config
mkdir -p logs
mkdir -p logs/temp

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo "警告: .env 文件不存在，请创建并配置 Webhook 信息"
    cat > .env << EOF
# Webhook 推送配置
WEBHOOK_UID=your_uid
WEBHOOK_TOKEN=your_token  
WEBHOOK_BASE_URL=https://your_uid.push.ft07.com/send/your_token.send
EOF
    echo "已创建示例 .env 文件，请编辑配置实际的 Webhook 信息"
fi

# 检查配置
echo "检查应用配置..."
uv run python -m src.maa_scheduler.main check-config

echo ""
echo "=== 开发环境准备完成 ==="
echo ""
echo "可用命令:"
echo "  启动完整服务:    uv run python -m src.maa_scheduler.main main"
echo "  仅启动调度器:    uv run python -m src.maa_scheduler.main start"  
echo "  仅启动Web界面:   uv run python -m src.maa_scheduler.main web"
echo "  检查配置:        uv run python -m src.maa_scheduler.main check-config"
echo "  列出任务:        uv run python -m src.maa_scheduler.main list-tasks"
echo "  测试通知:        uv run python -m src.maa_scheduler.main test notification"
echo ""
echo "Web界面地址: http://localhost:8080"
echo ""

# 询问是否立即启动服务
read -p "是否现在启动完整服务？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "启动服务..."
    uv run python -m src.maa_scheduler.main main
fi