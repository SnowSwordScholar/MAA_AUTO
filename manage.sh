#!/bin/bash
# MAA任务调度器管理脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_DIR="/Task/MAA_Auto"
SERVICE_NAME="maa-scheduler"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo "MAA任务调度器管理脚本"
    echo
    echo "用法: $0 {start|stop|restart|status|logs|enable|disable|install|uninstall}"
    echo
    echo "命令:"
    echo "  start     - 启动服务"
    echo "  stop      - 停止服务"
    echo "  restart   - 重启服务"
    echo "  status    - 查看服务状态"
    echo "  logs      - 查看服务日志"
    echo "  enable    - 启用开机自启"
    echo "  disable   - 禁用开机自启"
    echo "  install   - 安装服务"
    echo "  uninstall - 卸载服务"
    echo
    echo "任务管理:"
    echo "  list      - 列出所有任务"
    echo "  add       - 添加任务 (需要额外参数)"
    echo "  del       - 删除任务 (需要额外参数)"
}

# 检查服务状态
check_service_status() {
    if systemctl is-active --quiet $SERVICE_NAME; then
        return 0  # 运行中
    else
        return 1  # 未运行
    fi
}

# 启动服务
start_service() {
    log_info "启动MAA任务调度器服务..."
    
    if check_service_status; then
        log_warning "服务已在运行中"
        return 0
    fi
    
    systemctl start $SERVICE_NAME
    
    # 等待服务启动
    sleep 2
    
    if check_service_status; then
        log_success "服务启动成功"
    else
        log_error "服务启动失败"
        return 1
    fi
}

# 停止服务
stop_service() {
    log_info "停止MAA任务调度器服务..."
    
    if ! check_service_status; then
        log_warning "服务未在运行"
        return 0
    fi
    
    systemctl stop $SERVICE_NAME
    
    # 等待服务停止
    sleep 2
    
    if ! check_service_status; then
        log_success "服务停止成功"
    else
        log_error "服务停止失败"
        return 1
    fi
}

# 重启服务
restart_service() {
    log_info "重启MAA任务调度器服务..."
    
    systemctl restart $SERVICE_NAME
    
    # 等待服务重启
    sleep 3
    
    if check_service_status; then
        log_success "服务重启成功"
    else
        log_error "服务重启失败"
        return 1
    fi
}

# 查看服务状态
show_status() {
    log_info "MAA任务调度器服务状态:"
    echo
    systemctl status $SERVICE_NAME --no-pager
    echo
    
    # 显示任务状态
    log_info "任务状态:"
    cd $PROJECT_DIR
    python3 main.py status 2>/dev/null || log_warning "无法获取任务状态"
}

# 查看日志
show_logs() {
    log_info "显示MAA任务调度器日志 (按Ctrl+C退出):"
    journalctl -u $SERVICE_NAME -f
}

# 启用开机自启
enable_service() {
    log_info "启用MAA任务调度器开机自启..."
    
    systemctl enable $SERVICE_NAME
    
    if systemctl is-enabled --quiet $SERVICE_NAME; then
        log_success "开机自启已启用"
    else
        log_error "开机自启启用失败"
        return 1
    fi
}

# 禁用开机自启
disable_service() {
    log_info "禁用MAA任务调度器开机自启..."
    
    systemctl disable $SERVICE_NAME
    
    if ! systemctl is-enabled --quiet $SERVICE_NAME; then
        log_success "开机自启已禁用"
    else
        log_error "开机自启禁用失败"
        return 1
    fi
}

# 安装服务
install_service() {
    log_info "安装MAA任务调度器服务..."
    
    # 运行安装脚本
    bash $PROJECT_DIR/install.sh
}

# 卸载服务
uninstall_service() {
    log_info "卸载MAA任务调度器服务..."
    
    # 停止服务
    if check_service_status; then
        stop_service
    fi
    
    # 禁用服务
    if systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
        disable_service
    fi
    
    # 删除服务文件
    if [[ -f /etc/systemd/system/$SERVICE_NAME.service ]]; then
        rm -f /etc/systemd/system/$SERVICE_NAME.service
        systemctl daemon-reload
        log_success "服务文件已删除"
    fi
    
    log_success "服务卸载完成"
}

# 列出任务
list_tasks() {
    log_info "任务列表:"
    cd $PROJECT_DIR
    python3 main.py list
}

# 主函数
main() {
    case "${1:-}" in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        enable)
            enable_service
            ;;
        disable)
            disable_service
            ;;
        install)
            install_service
            ;;
        uninstall)
            uninstall_service
            ;;
        list)
            list_tasks
            ;;
        add)
            if [[ $# -lt 4 ]]; then
                log_error "用法: $0 add <任务名> <调度配置> <步骤...>"
                exit 1
            fi
            cd $PROJECT_DIR
            python3 main.py add "${@:2}"
            ;;
        del)
            if [[ $# -lt 2 ]]; then
                log_error "用法: $0 del <任务名>"
                exit 1
            fi
            cd $PROJECT_DIR
            python3 main.py del "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        "")
            show_help
            exit 1
            ;;
        *)
            log_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 检查是否为root用户
if [[ $EUID -ne 0 ]]; then
    log_error "此脚本需要root权限运行"
    exit 1
fi

# 运行主函数
main "$@"