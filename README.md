# MAA任务调度器 - 通用任务流程调度系统

一个现代化的自动化任务调度系统，专为游戏自动化和日常任务管理设计。

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![UV](https://img.shields.io/badge/UV-Package%20Manager-green.svg)](https://github.com/astral-sh/uv)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📖 简介

MAA任务调度器是一个功能强大的通用任务流程调度系统，提供：

### ✨ 核心特性

- 🕐 **灵活的时间调度**：支持间隔执行、时间窗口执行等多种调度模式
- 🔧 **可扩展的执行器**：支持ADB命令、系统命令、HTTP请求、文件操作等多种任务类型
- 📊 **实时任务监控**：支持关键词检测、WebHook通知等监控功能
- 🌐 **Web管理界面**：现代化响应式Web界面，支持暗黑模式和多语言
- 📱 **增强ADB控制**：屏幕保持唤醒、应用启动、分辨率检测等功能
- 🔄 **实时输出监控**：逐行命令输出监控和关键词自动检测
- 🐳 **容器化部署**：支持systemd服务和自动重启

## 🏗️ 项目结构

```
MAA_Auto/
├── src/maa_scheduler/          # 核心调度器包
│   ├── core/                   # 核心模块
│   │   ├── config_new.py      # 新版配置管理器
│   │   ├── executors.py       # 执行器框架
│   │   └── scheduler_new.py   # 新版调度器引擎
│   └── web/                   # Web管理界面
│       ├── app.py             # Flask Web应用
│       ├── templates/         # HTML模板
│       └── static/           # 静态资源
├── task_config.ini            # 任务配置文件 (新格式)
├── .env                       # 环境变量配置
├── main.py                    # 主入口文件
├── start_services.sh          # 服务启动脚本
├── stop_services.sh           # 服务停止脚本
├── install.sh                 # 安装脚本
├── manage.sh                  # 管理脚本
├── maa-scheduler.service      # systemd服务文件
└── pyproject.toml            # uv项目配置
```

## 🚀 快速开始

### 1. 环境要求

- **Python 3.8+**
- **uv** (推荐) 或 pip
- **systemd** (Linux服务部署)
- **ADB** (Android Debug Bridge)

### 2. 安装依赖

使用uv (推荐):
```bash
cd /Task/MAA_Auto
uv sync
```

或使用pip:
```bash
pip install flask requests python-dotenv
```

### 3. 配置环境变量

编辑 `.env` 文件：
```bash
# WebHook配置
WEBHOOK_DINGDING_URL=https://oapi.dingtalk.com/robot/send?access_token=your_token
WEBHOOK_FEISHU_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_id

# 系统配置
ADB_DEVICE=localhost:35555
MAA_PATH=/path/to/maa
```

### 4. 启动服务

#### 🎯 方式一：systemd服务 (推荐)

```bash
# 安装系统服务
sudo ./install.sh

# 启动服务 (同时启动调度器和Web界面)
sudo ./manage.sh start

# 查看状态
sudo ./manage.sh status

# 查看日志
sudo ./manage.sh logs

# 启用开机自启
sudo ./manage.sh enable
```

#### 🖥️ 方式二：直接运行

```bash
# 启动调度器 (后台运行)
nohup uv run python main.py run &

# 启动Web界面 (另开终端)
uv run python src/maa_scheduler/web/app.py
```

#### 🔧 方式三：使用启动脚本

```bash
# 同时启动调度器和Web界面
./start_services.sh

# 停止所有服务
./stop_services.sh
```

## 🌐 Web管理界面

启动服务后，访问：
- **本地访问**: http://localhost:5000
- **局域网访问**: http://your_ip:5000

### 界面功能

- 📊 **任务监控面板**: 实时查看任务状态和执行情况
- ⚙️ **任务管理**: 启动、停止、查看任务详情
- 📝 **实时日志**: 查看系统和任务执行日志
- 🎨 **暗黑模式**: 支持明暗主题切换
- 🌍 **多语言**: 中英文界面自动切换

## 🔧 配置说明

### 任务流程配置

在 `task_config.ini` 的 `[TaskFlow]` 部分定义任务调度：

```ini
[TaskFlow]
# 任务名称 = 类型|时间参数|优先级|随机延迟范围|队列组
maa_roguelike = timewindow|5-4|1|0-300|maa_group
recruitment = interval|9.5h|2|60-180|daily_group
clear_stamina = timewindow|3-3.5|3|30-90|daily_group
```

**调度类型:**
- `interval`: 间隔执行 (如: `2h`, `30m`, `120s`)
- `timewindow`: 时间窗口执行 (如: `5-23` 表示5点到23点之间)

### 任务负载配置

在 `[TaskPayloads]` 部分定义任务执行步骤：

```ini
[TaskPayloads]
maa_roguelike = [
    {"type": "adb_keep_awake", "params": [], "options": {"timeout": 10}},
    {"type": "adb_start_app", "params": ["com.hypergryph.arknights"], "options": {}},
    {"type": "command", "params": ["./MAA", "--roguelike"], "options": {"log": true}},
    {"type": "webhook", "params": ["success"], "options": {"content": "肉鸽任务完成"}}
]
```

## 🔧 支持的执行器类型

### ADB执行器
- `adb_keep_awake`: 唤醒设备屏幕并保持
- `adb_start_app`: 启动指定应用
- `resolution_check`: 获取设备分辨率

### 命令执行器
- `command`: 执行系统命令 (支持实时输出)
- `wait`: 等待指定时间

### HTTP执行器
- `http_get`: HTTP GET请求
- `http_post`: HTTP POST请求
- `webhook`: 发送WebHook通知

### 文件执行器
- `file_write`: 写入文件
- `file_read`: 读取文件
- `file_copy`: 复制文件
- `file_delete`: 删除文件

## 📈 监控功能

### 关键词检测

在 `[TaskKeywords]` 部分配置关键词检测：

```ini
[TaskKeywords]
maa_roguelike = {
    "success": {
        "keywords": ["完成", "成功", "finished"],
        "action": "webhook=success"
    },
    "error": {
        "keywords": ["错误", "失败", "error"],
        "action": "webhook=error"
    }
}
```

### WebHook通知

在 `[WebhookTemplates]` 部分配置通知模板：

```ini
[WebhookTemplates]
success = {
    "url": "${WEBHOOK_DINGDING_URL}",
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "data": {
        "msgtype": "text",
        "text": {"content": "✅ 任务执行成功: {{content}}"}
    }
}
```

## 🛠️ 命令行工具

### 基本命令

```bash
# 查看任务状态
uv run python main.py status

# 列出所有任务
uv run python main.py list

# 测试配置文件
uv run python main.py test

# 运行调度器
uv run python main.py run
```

### 服务管理 (需要root权限)

```bash
# 使用管理脚本
sudo ./manage.sh start         # 启动服务
sudo ./manage.sh stop          # 停止服务
sudo ./manage.sh restart       # 重启服务
sudo ./manage.sh status        # 查看状态
sudo ./manage.sh logs          # 查看日志
sudo ./manage.sh enable        # 启用开机自启
sudo ./manage.sh disable       # 禁用开机自启

# 任务管理
sudo ./manage.sh list          # 列出任务
```

## 📁 日志管理

日志文件位置：
- **应用日志**: `logs/scheduler.log`, `logs/web.log`
- **系统日志**: `journalctl -u maa-scheduler`

日志级别可在 `task_config.ini` 中配置：
```ini
[SystemSettings]
log_level = INFO  # DEBUG, INFO, WARNING, ERROR
```

## ⚠️ 安全注意事项

**重要警告**：本项目Web界面无用户认证机制，请注意安全。

### 安全建议：

1. **仅本地访问**：确保Web服务仅绑定到localhost (127.0.0.1)
2. **防火墙保护**：不要在路由器或防火墙中开放5000端口
3. **内网隔离**：如需局域网访问，确保网络环境安全
4. **VPN访问**：远程管理请使用VPN连接后访问

```bash
# 检查服务绑定（推荐仅绑定本地）
netstat -tlnp | grep :5000
```

## 🔄 扩展开发

### 添加新的执行器

1. 继承 `TaskExecutor` 基类
2. 实现 `get_supported_steps()` 和 `execute_step()` 方法
3. 在调度器中注册新执行器

示例：
```python
class CustomExecutor(TaskExecutor):
    def get_supported_steps(self) -> List[str]:
        return ['custom_action']
    
    def execute_step(self, step_type: str, params: List[Any], options: Dict[str, Any]) -> Tuple[bool, str]:
        if step_type == 'custom_action':
            # 自定义逻辑
            return True, "执行成功"
        return False, "不支持的步骤类型"
```

## 🐛 故障排除

### 常见问题

1. **模块导入错误**
   - 确保已正确安装依赖: `uv sync`
   - 检查Python路径配置

2. **ADB连接失败**
   - 确认设备已连接: `adb devices`
   - 检查 `.env` 中的 `ADB_DEVICE` 配置

3. **任务不执行**
   - 检查任务调度配置格式
   - 查看日志文件排查错误: `sudo ./manage.sh logs`

4. **WebHook通知失败**
   - 验证WebHook URL的有效性
   - 检查网络连接和防火墙设置

5. **Web界面无法访问**
   - 检查端口5000是否被占用: `netstat -tlnp | grep :5000`
   - 确认服务是否正常启动: `sudo ./manage.sh status`

### 调试模式

启用详细日志：
```ini
[SystemSettings]
log_level = DEBUG
```

查看实时日志：
```bash
# 查看系统日志
sudo ./manage.sh logs

# 查看应用日志
tail -f logs/scheduler.log
tail -f logs/web.log
```

## 🔗 相关项目

- [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights) - 明日方舟小助手
- [BAAH](https://github.com/BlueArchiveArisHelper/BAAH) - 碧蓝档案爱丽丝助手

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

---

## 🎯 快速启动步骤总结

1. **安装系统服务**：`sudo ./install.sh`
2. **启动服务**：`sudo ./manage.sh start`
3. **访问Web界面**：http://localhost:5000
4. **查看状态**：`sudo ./manage.sh status`
5. **查看日志**：`sudo ./manage.sh logs`

**一条命令启动全部**：
```bash
sudo ./install.sh && sudo ./manage.sh start && echo "服务已启动，访问 http://localhost:5000"
```

---

*MAA任务调度器 v2.0.0 - 让自动化更简单* 🚀