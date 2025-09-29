#!/bin/bash
# MAA任务调度器 - 快速启动脚本

cd "$(dirname "$0")"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 显示横幅
echo -e "${PURPLE}"
echo "=================================================="
echo "        MAA任务调度器 - 快速启动工具"
echo "=================================================="
echo -e "${NC}"

# 检查uv是否安装
if ! command -v uv &> /dev/null; then
    echo -e "${RED}❌ 错误: uv 未安装${NC}"
    echo "请先安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 显示菜单
echo -e "${CYAN}请选择启动模式:${NC}"
echo "1) 🌐 Web界面模式 (推荐)"
echo "2) 🔄 调度器模式 (后台运行)"
echo "3) 📊 查看系统状态"
echo "4) 📋 管理任务"
echo "5) 🔔 发送测试通知"
echo "6) 🛠️ 系统服务管理"
echo "7) 📖 查看帮助"
echo "0) 退出"
echo

read -p "请输入选项 (0-7): " choice

case $choice in
    1)
        echo -e "${GREEN}🌐 启动Web界面模式...${NC}"
        echo "访问地址: http://127.0.0.1:8080"
        echo "按 Ctrl+C 停止服务"
        echo ""
        uv run python -m src.maa_scheduler.main web --host 127.0.0.1  
        ;;
    2)
        echo -e "${GREEN}🔄 启动调度器模式...${NC}"
        echo "调度器将在后台运行任务"
        echo "按 Ctrl+C 停止调度器"
        echo ""
        uv run python -m src.maa_scheduler.main start
        ;;
    3)
        echo -e "${BLUE}📊 系统状态:${NC}"
        uv run python -m src.maa_scheduler.main status
        ;;
    4)
        echo -e "${BLUE}📋 任务管理:${NC}"
        echo "1) 列出所有任务"
        echo "2) 创建新任务"
        echo "3) 运行指定任务"
        echo ""
        read -p "请选择操作: " task_choice
        case $task_choice in
            1)
                uv run python -m src.maa_scheduler.main task list
                ;;
            2)
                read -p "任务名称: " task_name
                read -p "Cron表达式 (如: 0 9 * * *): " cron_expr
                uv run python -m src.maa_scheduler.main task create "$task_name" --trigger cron --cron "$cron_expr"
                ;;
            3)
                read -p "任务ID: " task_id
                uv run python -m src.maa_scheduler.main task run "$task_id"
                ;;
            *)
                echo "无效选项"
                ;;
        esac
        ;;
    5)
        echo -e "${YELLOW}🔔 发送测试通知...${NC}"
        uv run python -m src.maa_scheduler.main test-notification
        ;;
    6)
        echo -e "${PURPLE}🛠️ 系统服务管理:${NC}"
        echo "1) 安装systemd服务"
        echo "2) 启动服务"
        echo "3) 停止服务"
        echo "4) 查看服务状态"
        echo ""
        read -p "请选择操作: " service_choice
        case $service_choice in
            1)
                echo "安装systemd服务需要root权限..."
                sudo chmod +x scripts/install_service.sh
                sudo scripts/install_service.sh
                ;;
            2)
                sudo systemctl start maa-scheduler
                sudo systemctl status maa-scheduler
                ;;
            3)
                sudo systemctl stop maa-scheduler
                ;;
            4)
                sudo systemctl status maa-scheduler
                ;;
            *)
                echo "无效选项"
                ;;
        esac
        ;;
    7)
        echo -e "${BLUE}📖 帮助信息:${NC}"
        echo ""
        echo -e "${GREEN}📁 项目结构:${NC}"
        echo "  config/     - 配置文件目录"
        echo "  logs/       - 日志文件目录" 
        echo "  scripts/    - 部署脚本目录"
        echo "  src/        - 源代码目录"
        echo ""
        echo -e "${GREEN}🌐 Web界面功能:${NC}"
        echo "  /           - 仪表板"
        echo "  /tasks      - 任务管理"
        echo "  /monitor    - 实时监控"
        echo "  /logs       - 日志查看"
        echo "  /settings   - 系统设置"
        echo ""
        echo -e "${GREEN}📋 CLI命令:${NC}"
        uv run python -m src.maa_scheduler.main --help
        ;;
    0)
        echo -e "${GREEN}👋 再见!${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ 无效选项${NC}"
        exit 1
        ;;
esac