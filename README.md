# MAA/BAAH 任务调度器

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-managed-36393f?logo=astral&logoColor=white)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

[:us: English README](README_en.md)

> 基于 systemd 的终端程序调度与自启动方案

项目最初用于调度 MAA 自动化任务，如今已扩展到 BAAH 以及其他可部署的终端程序。通过统一的队列、触发器和 Web 管理界面，可以在同一套流程里排程多种脚本或命令行工具。



## 功能特性

### 核心功能
- **灵活的任务调度**: 时间段、间隔执行、随机时间三种触发方式
- **资源分组管理**: 防止硬件资源冲突，支持并发控制
- **任务队列系统**: 基于优先级的智能任务调度
- **可扩展任务类型**: 通过配置即可接入任意 CLI/脚本任务（含 MAA、BAAH 等）
- **智能重试策略**: 支持失败重试与时间窗口内的成功重试配置
- **实时监控**: Web 界面实时显示任务状态和系统信息
- **日志管理**: 全局日志和任务独立日志，支持关键词监控
- **通知推送**: 基于 Webhook 的任务状态通知
- **模式切换**: 自动调度模式和单任务手动执行模式
- *竖屏模式操作支持**: 有竖屏操作支持

### 任务类型支持
- **普通任务**: 执行任意命令和脚本，可用于 BAAH 或其他终端工具
- **模拟器任务**: 自动控制 ADB 设备，设置分辨率，启动应用（常用于 MAA 和 BAAH 的切换）

### Web 控制界面
- 任务管理：创建、编辑、删除、执行任务
- 实时监控：查看任务状态、系统资源使用情况
- 日志查看：实时查看任务执行日志
- 系统设置：调度器配置、通知设置

### 通知
- 通知使用 Server 酱³ 或者其他可用的 WebHook 应用

## 快速开始

### 1. 环境准备

确保系统已安装 Python 3.9+ 和 uv：

```bash
# 安装 uv（如果未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 项目配置

1. 克隆项目并进入目录：
```bash
cd /Task/MAA_Auto
```

2. 配置环境变量（编辑 `.env` 文件）：
```env
# Webhook 推送配置
WEBHOOK_UID=your_uid
WEBHOOK_TOKEN=your_token
WEBHOOK_BASE_URL=https://your_uid.push.ft07.com/send/your_token.send
```

3. 编辑任务配置（`config/tasks.yaml`）：
   - 为 MAA 任务保留原有的触发器与资源组设置；
   - 针对 BAAH 或其他命令行程序，填写对应的执行命令和运行参数；
   - 所有任务都可复用相同的重试策略与通知机制。

### 3. 安装依赖

```bash
# 使用 uv 安装依赖
uv sync
```

### 4. 初始化配置

```bash
# 检查配置
uv run python -m src.maa_scheduler.main check-config
```

### 5. 启动服务

```bash
# 启动完整服务（调度器 + Web 界面）
uv run python -m src.maa_scheduler.main main

# 仅启动调度器
uv run python -m src.maa_scheduler.main start

# 仅启动 Web 界面
uv run python -m src.maa_scheduler.main web
```

### 6. 访问 Web 界面

打开浏览器访问：http://localhost:8080

## 命令行使用

### 基本命令

```bash
# 查看帮助
uv run python -m src.maa_scheduler.main --help

# 检查配置
uv run python -m src.maa_scheduler.main check-config

# 列出所有任务
uv run python -m src.maa_scheduler.main list-tasks

# 测试通知功能
uv run python -m src.maa_scheduler.main test notification
```

### 服务管理

```bash
# 启动完整服务
uv run python -m src.maa_scheduler.main main

# 启动调度器（无 Web 界面）
uv run python -m src.maa_scheduler.main start

# 启动 Web 界面（无调度器）
uv run python -m src.maa_scheduler.main web --host 0.0.0.0 --port 8080

# 仅启动 Web 界面
uv run python -m src.maa_scheduler.main main --web-only
```

## 系统集成

### systemctl 服务配置

项目内提供了一个可直接复制的示例单元文件：`config/systemd/maa-scheduler.service`。

1. 复制示例文件并根据实际环境调整：
```bash
sudo cp config/systemd/maa-scheduler.service /etc/systemd/system/maa-scheduler.service
sudo chown root:root /etc/systemd/system/maa-scheduler.service
```

2. 编辑服务文件，修改运行用户、工作目录与 uv 路径：
```ini
[Unit]
Description=MAA Task Scheduler
After=network.target
Wants=network.target

[Service]
Type=exec
User=your_username
Group=your_group
WorkingDirectory=/Task/MAA_Auto
Environment=PATH=/home/your_username/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/your_username/.local/bin/uv run python -m src.maa_scheduler.main main
Restart=always
RestartSec=10
KillMode=mixed
TimeoutStopSec=5

[Install]
WantedBy=multi-user.target
```

3. 重新加载 systemd 并启用开机自启动：
```bash
sudo systemctl daemon-reload
sudo systemctl enable maa-scheduler.service
sudo systemctl start maa-scheduler.service
```

4. 查看服务状态：
```bash
sudo systemctl status maa-scheduler.service
```



## API 接口

### 系统状态
- `GET /api/status` - 获取系统状态
- `POST /api/scheduler/start` - 启动调度器
- `POST /api/scheduler/stop` - 停止调度器
- `POST /api/scheduler/mode` - 设置调度器模式

### 任务管理
- `GET /api/tasks` - 获取任务列表
- `POST /api/tasks` - 创建任务
- `GET /api/tasks/{task_id}` - 获取任务详情
- `PUT /api/tasks/{task_id}` - 更新任务
- `DELETE /api/tasks/{task_id}` - 删除任务
- `POST /api/tasks/{task_id}/run` - 执行任务
- `POST /api/tasks/{task_id}/cancel` - 取消任务

### 日志和监控
- `GET /api/logs/{task_id}` - 获取任务日志
- `GET /api/resource-groups` - 获取资源分组状态

### 通知测试
- `POST /api/test-notification` - 发送测试通知

## 故障排除

### 常见问题

1. **任务无法执行**
   - 检查资源分组配置
   - 确认调度器处于正确模式
   - 查看任务日志

2. **通知发送失败**
   - 验证 Webhook 配置
   - 检查网络连接
   - 使用测试通知功能

3. **Web 界面无法访问**
   - 检查端口占用
   - 确认防火墙设置
   - 查看服务日志

### 日志位置
- 应用日志：`logs/maa_scheduler.log`
- 任务临时日志：`logs/temp/task_*_*.log`
- 系统服务日志：`journalctl -u maa-scheduler.service`

## 开发和贡献

### 项目结构
```
src/maa_scheduler/
├── __init__.py          # 包初始化
├── main.py             # 主程序入口
├── config.py           # 配置管理
├── scheduler.py        # 任务调度器
├── executor.py         # 任务执行器
├── notification.py     # 通知服务
├── web_ui.py          # Web 界面
├── static
│   ├── css
│   │   └── main.css
│   └── js
│       └── i18n.js    # 多语言
└── templates/         # HTML 模板
    ├── base.html
    ├── index.html
    └── tasks.html
```

### 开发环境设置
```bash
# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest

# 代码格式化
uv run black src/
uv run flake8 src/
```

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 更新日志

### v1.0
- 初始版本发布
- 基础任务调度功能
- 通知推送支持
- systemctl 集成

### v2.0
- 使用 Web 作为控制页面
- 添加了竖屏操作支持
- 支持丰富详细的自定义功能支持