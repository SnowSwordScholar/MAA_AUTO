#!/bin/bash
# MAA任务调度器安装脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要root权限运行"
        exit 1
    fi
}

# 检查Python环境
check_python() {
    log_info "检查Python环境..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python3未安装"
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2)
    log_success "Python版本: $python_version"
    
    # 检查uv
    if ! command -v uv &> /dev/null; then
        log_warning "uv未安装，正在安装..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        source ~/.bashrc
    fi
    
    log_success "uv已安装"
}

# 安装依赖
install_dependencies() {
    log_info "安装项目依赖..."
    
    cd /Task/MAA_Auto
    
    # 使用uv安装依赖
    uv sync
    
    log_success "依赖安装完成"
}

# 配置环境文件
setup_env() {
    log_info "配置环境文件..."
    
    cd /Task/MAA_Auto
    
    if [[ ! -f .env ]]; then
        log_warning ".env文件不存在，创建默认配置"
        cp .env.example .env 2>/dev/null || true
    fi
    
    log_success "环境文件配置完成"
}

# 安装systemd服务
install_service() {
    log_info "安装systemd服务..."
    
    # 复制服务文件
    cp /Task/MAA_Auto/maa-scheduler.service /etc/systemd/system/
    
    # 重新加载systemd
    systemctl daemon-reload
    
    # 启用服务
    systemctl enable maa-scheduler.service
    
    log_success "systemd服务安装完成"
}

# 创建日志目录
setup_logs() {
    log_info "创建日志目录..."
    
    mkdir -p /Task/MAA_Auto/logs
    chmod 755 /Task/MAA_Auto/logs
    
    log_success "日志目录创建完成"
}

# 设置脚本权限
setup_permissions() {
    log_info "设置脚本权限..."
    
    cd /Task/MAA_Auto
    chmod +x start_services.sh
    chmod +x stop_services.sh
    chmod +x manage.sh
    chmod +x install.sh
    
    log_success "脚本权限设置完成"
}

# 主函数
main() {
    log_info "开始安装MAA任务调度器..."
    
    check_root
    check_python
    install_dependencies
    setup_env
    setup_logs
    setup_permissions
    install_service
    
    log_success "MAA任务调度器安装完成！"
    echo
    log_info "使用以下命令管理服务 (推荐):"
    echo "  启动服务 (调度器+Web): ./manage.sh start"
    echo "  停止服务: ./manage.sh stop"
    echo "  查看状态: ./manage.sh status"
    echo "  查看日志: ./manage.sh logs"
    echo "  启用开机自启: ./manage.sh enable"
    echo
    log_info "或使用systemctl命令:"
    echo "  启动服务: systemctl start maa-scheduler"
    echo "  停止服务: systemctl stop maa-scheduler"
    echo "  查看状态: systemctl status maa-scheduler"
    echo "  查看日志: journalctl -u maa-scheduler -f"
    echo
    log_info "Web管理界面:"
    echo "  本地访问: http://localhost:5000"
    echo "  局域网访问: http://$(hostname -I | awk '{print $1}'):5000"
    echo
    log_info "使用以下命令管理任务:"
    echo "  查看任务状态: ./manage.sh list"
    echo "  测试配置: uv run python main.py test"
    echo
    log_warning "请在启动服务前确保:"
    echo "  1. 编辑 /Task/MAA_Auto/.env 文件，填入正确的配置"
    echo "  2. 编辑 /Task/MAA_Auto/task_config.ini 文件，配置任务"
    echo "  3. 确保ADB设备已正确连接"
}

# 运行主函数
main "$@"