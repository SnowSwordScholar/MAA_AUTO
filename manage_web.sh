#!/bin/bash
# MAA Web管理器安装和管理脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="maa-web-manager.service"
SERVICE_NAME="maa-web-manager"
INSTALL_PATH="/etc/systemd/system"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用root权限运行此脚本"
        exit 1
    fi
}

# 安装依赖
install_dependencies() {
    print_info "检查并安装Python依赖..."
    
    # 检查pip是否安装
    if ! command -v pip3 &> /dev/null; then
        print_info "安装pip3..."
        apt update
        apt install -y python3-pip
    fi
    
    # 安装Flask和相关依赖
    pip3 install flask requests configparser pathlib
    
    print_success "依赖安装完成"
}

# 安装服务
install_service() {
    print_info "安装MAA Web管理器服务..."
    
    # 检查服务文件是否存在
    if [ ! -f "$SCRIPT_DIR/$SERVICE_FILE" ]; then
        print_error "服务文件 $SERVICE_FILE 不存在"
        exit 1
    fi
    
    # 复制服务文件
    cp "$SCRIPT_DIR/$SERVICE_FILE" "$INSTALL_PATH/"
    
    # 重新加载systemd配置
    systemctl daemon-reload
    
    # 启用服务
    systemctl enable $SERVICE_NAME
    
    print_success "服务安装完成"
}

# 启动服务
start_service() {
    print_info "启动MAA Web管理器服务..."
    
    systemctl start $SERVICE_NAME
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        print_success "服务启动成功"
        print_info "Web管理界面: http://localhost:5000"
    else
        print_error "服务启动失败"
        print_info "查看日志: journalctl -u $SERVICE_NAME -f"
        exit 1
    fi
}

# 停止服务
stop_service() {
    print_info "停止MAA Web管理器服务..."
    systemctl stop $SERVICE_NAME
    print_success "服务已停止"
}

# 重启服务
restart_service() {
    print_info "重启MAA Web管理器服务..."
    systemctl restart $SERVICE_NAME
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        print_success "服务重启成功"
    else
        print_error "服务重启失败"
        exit 1
    fi
}

# 查看服务状态
status_service() {
    print_info "MAA Web管理器服务状态:"
    systemctl status $SERVICE_NAME --no-pager
}

# 查看日志
logs_service() {
    print_info "MAA Web管理器服务日志:"
    journalctl -u $SERVICE_NAME -f
}

# 卸载服务
uninstall_service() {
    print_info "卸载MAA Web管理器服务..."
    
    # 停止并禁用服务
    systemctl stop $SERVICE_NAME 2>/dev/null || true
    systemctl disable $SERVICE_NAME 2>/dev/null || true
    
    # 删除服务文件
    rm -f "$INSTALL_PATH/$SERVICE_FILE"
    
    # 重新加载systemd配置
    systemctl daemon-reload
    
    print_success "服务卸载完成"
}

# 显示帮助
show_help() {
    echo "MAA Web管理器管理脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  install     安装服务（包含依赖安装）"
    echo "  start       启动服务"
    echo "  stop        停止服务"
    echo "  restart     重启服务"
    echo "  status      查看服务状态"
    echo "  logs        查看服务日志"
    echo "  uninstall   卸载服务"
    echo "  help        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 install    # 安装并启动服务"
    echo "  $0 status     # 查看服务状态"
    echo "  $0 logs       # 实时查看日志"
}

# 主函数
main() {
    case "${1:-help}" in
        install)
            check_root
            install_dependencies
            install_service
            start_service
            ;;
        start)
            check_root
            start_service
            ;;
        stop)
            check_root
            stop_service
            ;;
        restart)
            check_root
            restart_service
            ;;
        status)
            status_service
            ;;
        logs)
            logs_service
            ;;
        uninstall)
            check_root
            uninstall_service
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"