# MAA Auto - 双游戏自动化管理系统

一个专为 Linux 环境设计的游戏自动化管理系统，支持明日方舟（Arknights）和蔚蓝档案（BlueArchive）的轮流自动化操作，并提供直观的 Web 管理界面。

## ✨ 核心特性

- **双游戏轮流执行**：智能调度明日方舟（MAA）和蔚蓝档案（BAAH）的自动化任务
- **Web 管理界面**：提供配置管理、日志查看、任务监控等功能
- **时间窗口管理**：支持自定义游戏运行时间段，避免冲突
- **智能错误处理**：自动错误检测和重启机制
- **推送通知支持**：集成 Server 酱等推送服务
- **完整日志系统**：详细的运行日志记录和 Web 端查看
- **Linux 原生优化**：专为 Linux 环境优化，支持 ARM 架构

## 🏗️ 系统架构

本项目采用模块化设计：
- `maa_auto.py` - 核心自动化调度引擎
- `web_manager.py` - Web 管理界面后端
- `templates/` - Web 界面模板
- `config.example.ini` - 配置文件模板

## 📋 运行前提

在使用本项目前，请确保以下组件已正确安装和配置：

### MAA（明日方舟助手）
- MAA 内核安装在 `/root/.cargo/bin/maa`
- 官方 Linux 版本文件安装在 `/Task/MAA/`
- Python 脚本位于 `/Task/MAA/Python/`
- 已安装并配置好 `uv` 环境

### BAAH（蔚蓝档案助手）
- BAAH 文件放置在 `/Task/BAAH/`
- 已配置好 `task.json` 文件

### 系统环境
- **操作系统**：Debian 12 或兼容的 Linux 发行版
- **Python**：3.8+ 版本
- **ADB**：用于 Android 设备连接
- **模拟器**：推荐使用 Redroid（开发环境使用 Orangepi5plus + Armbian）

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone <repository-url>
cd MAA_Auto
```

### 2. 安装依赖
```bash
pip install flask schedule requests
```

### 3. 配置系统
```bash
# 复制配置文件模板
cp config.example.ini config.ini

# 编辑配置文件（详细配置说明见配置文件内注释）
nano config.ini
```

### 4. 启动服务

#### 方式一：直接运行
```bash
# 启动自动化任务
python maa_auto.py

# 启动 Web 界面（另开终端）
python web_manager.py
```

#### 方式二：系统服务（推荐）
```bash
# 安装系统服务
sudo cp maa-web-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable maa-web-manager
sudo systemctl start maa-web-manager
```

## 🔧 配置说明

项目目前处于快速开发阶段，请参考 `config.example.ini` 进行配置。配置文件包含以下主要部分：

- **MAA 配置**：ADB 连接、MAA 命令、超时设置等
- **调度配置**：运行时间窗口、重启延迟等
- **错误处理**：错误阈值、时间窗口等
- **通知配置**：推送服务设置
- **公招配置**：公开招募自动化
- **日常任务**：体力清理、材料获取等
- **BAAH 配置**：蔚蓝档案相关设置

详细配置说明请查看配置文件内的注释。

## 🌐 Web 界面

访问 `http://localhost:5000` 使用 Web 管理界面，提供以下功能：

- **任务监控**：实时查看任务运行状态
- **配置管理**：在线编辑配置文件
- **日志查看**：浏览运行日志和错误信息
- **手动控制**：启动/停止特定任务

## ⚠️ 安全注意事项

**重要警告**：本项目未实现用户认证机制，Web 界面可被任何能访问的用户控制。

### 安全建议：
1. **仅本地访问**：确保 Web 服务仅绑定到 localhost (127.0.0.1)
2. **防火墙保护**：不要在路由器或防火墙中开放相关端口
3. **内网隔离**：如需局域网访问，确保网络环境安全
4. **VPN 访问**：远程管理请使用 VPN 连接后访问

```bash
# 检查服务绑定（推荐仅绑定本地）
netstat -tlnp | grep :5000
```

## 📁 项目结构

```
MAA_Auto/
├── maa_auto.py              # 主自动化脚本
├── web_manager.py           # Web 界面后端
├── config.example.ini       # 配置文件模板
├── config.ini              # 实际配置文件（需自创建）
├── maa-web-manager.service # systemd 服务文件
├── manage_web.sh           # Web 服务管理脚本
├── test_web_manager.py     # Web 服务测试脚本
├── templates/              # Web 界面模板
│   ├── base.html
│   ├── index.html
│   ├── config.html
│   ├── logs.html
│   └── tasks.html
└── logs/                   # 日志文件目录
    ├── maa_auto.log
    └── web_manager.log
```

## 🔄 工作原理

1. **时间窗口调度**：根据配置的时间窗口，系统自动在 MAA 和 BAAH 之间切换
2. **智能监控**：监控游戏进程状态，自动处理异常情况
3. **任务队列**：按优先级执行日常任务、公招任务等
4. **状态同步**：Web 界面实时显示当前运行状态和日志

## 🐛 故障排除

### 常见问题：
1. **ADB 连接失败**：检查模拟器状态和 ADB 配置
2. **MAA/BAAH 路径错误**：确认安装路径与配置文件一致
3. **权限问题**：确保脚本有足够权限访问相关目录
4. **端口占用**：检查 5000 端口是否被其他服务占用

### 日志查看：
```bash
# 查看主程序日志
tail -f logs/maa_auto.log

# 查看 Web 服务日志
tail -f logs/web_manager.log
```

## 🤝 开发环境

- **开发平台**：Orangepi5plus + Armbian
- **模拟器**：Redroid
- **测试环境**：Debian 12

## 📝 许可证

本项目遵循开源许可证，具体信息请查看 LICENSE 文件。

## 🔗 相关项目

- [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights) - 《明日方舟》小助手
- [BAAH](https://github.com/BlueArchiveArisHelper/BAAH) - 碧蓝档案爱丽丝助手

---

**注意**：本项目仅供学习交流使用，请遵守相关游戏的使用条款。
