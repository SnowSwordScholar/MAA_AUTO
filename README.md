# MAA任务调度器 - 通用任务流程调度系统# MAA任务调度器 - 通用任务流程调度系统



## 📖 简介## 📖 简介



MAA任务调度器是一个通用的任务流程调度系统，专为自动化场景设计。支持灵活的时间调度、可扩展的执行器框架、实时任务监控等功能。MAA任务调度器是一个通用的任务流程调度系统，专为自动化场景设计。它支持：



### ✨ 核心特性- 🕐 **灵活的时间调度**：支持间隔执行、时间窗口执行等多种调度模式

- 🔧 **可扩展的执行器**：支持ADB命令、系统命令、HTTP请求、文件操作等多种任务类型

- 🕐 **灵活的时间调度**：支持间隔执行、时间窗口执行等多种调度模式- 📊 **实时任务监控**：支持关键词检测、WebHook通知等监控功能

- 🔧 **可扩展的执行器**：支持ADB命令、系统命令、HTTP请求、文件操作等多种任务类型- 🌐 **Web管理界面**：提供友好的Web界面进行任务管理(计划中)

- 📊 **实时任务监控**：支持关键词检测、WebHook通知等监控功能## 🏗️ 项目结构

- 🌐 **Web管理界面**：提供友好的Web界面进行任务管理(计划中)

- 🐳 **容器化部署**：支持Docker和systemd服务部署```

MAA_Auto/

## 🏗️ 项目结构├── src/maa_scheduler/          # 核心调度器包

│   ├── core/                   # 核心模块

```│   │   ├── config.py          # 配置管理

MAA_Auto/│   │   ├── executors.py       # 执行器框架

├── src/maa_scheduler/          # 核心调度器包│   │   └── scheduler.py       # 调度器引擎

│   ├── core/                   # 核心模块│   └── web/                   # Web界面(计划中)

│   │   ├── config.py          # 配置管理├── task_config.ini            # 任务配置文件

│   │   ├── executors.py       # 执行器框架├── .env                       # 环境变量配置

│   │   └── scheduler.py       # 调度器引擎├── main.py                    # 主入口文件

│   └── web/                   # Web界面(计划中)├── install.sh                 # 安装脚本

├── task_config.ini            # 任务配置文件├── manage.sh                  # 管理脚本

├── .env                       # 环境变量配置├── maa-scheduler.service      # systemd服务文件

├── main.py                    # 主入口文件└── pyproject.toml            # uv项目配置

├── install.sh                 # 安装脚本

├── manage.sh                  # 管理脚本```

├── maa-scheduler.service      # systemd服务文件

└── pyproject.toml            # uv项目配置## 🚀 快速开始

```

### 1. 环境要求

## 🚀 快速开始

- Python 3.8+

### 1. 环境要求- uv (推荐) 或 pip

- systemd (Linux服务部署)

- Python 3.8+

- uv (推荐) 或 pip### 2. 安装依赖

- systemd (Linux服务部署)

使用uv (推荐):

### 2. 安装依赖```bash

cd /Task/MAA_Auto

```bashuv sync

cd /Task/MAA_Auto```

uv sync

```或使用pip:

```bash

### 3. 配置环境变量pip install flask requests python-dotenv

```

编辑 `.env` 文件：

```bash### 2. 安装依赖

# WebHook配置```bash

WEBHOOK_DINGDING_URL=https://oapi.dingtalk.com/robot/send?access_token=your_tokenpip install flask schedule requests

WEBHOOK_FEISHU_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_id```



# 系统配置### 3. 配置系统

ADB_DEVICE=localhost:35555```bash

MAA_PATH=/path/to/maa# 复制配置文件模板

```cp config.example.ini config.ini



### 4. 运行调度器# 编辑配置文件（详细配置说明见配置文件内注释）

nano config.ini

**前台运行:**```

```bash

uv run python main.py run### 4. 启动服务

```

#### 方式一：直接运行

**安装为系统服务:**```bash

```bash# 启动自动化任务

# 安装服务python maa_auto.py

sudo ./install.sh

# 启动 Web 界面（另开终端）

# 管理服务python web_manager.py

sudo ./manage.sh start      # 启动```

sudo ./manage.sh stop       # 停止

sudo ./manage.sh status     # 状态#### 方式二：系统服务（推荐）

sudo ./manage.sh logs       # 日志```bash

```# 安装系统服务

sudo cp maa-web-manager.service /etc/systemd/system/

## 📋 任务配置sudo systemctl daemon-reload

sudo systemctl enable maa-web-manager

### 任务调度配置sudo systemctl start maa-web-manager

```

在 `task_config.ini` 的 `[TaskSchedule]` 部分定义任务调度：

## 🔧 配置说明

```ini

[TaskSchedule]项目目前处于快速开发阶段，请参考 `config.example.ini` 进行配置。配置文件包含以下主要部分：

# 任务名称 = 类型|时间参数|优先级|随机延迟范围|队列组

my_task = interval|2h|1|0-300|default_group- **MAA 配置**：ADB 连接、MAA 命令、超时设置等

daily_task = timewindow|5-23|2|60-120|daily_group- **调度配置**：运行时间窗口、重启延迟等

```- **错误处理**：错误阈值、时间窗口等

- **通知配置**：推送服务设置

**调度类型:**- **公招配置**：公开招募自动化

- `interval`: 间隔执行 (如: `2h`, `30m`, `120s`)- **日常任务**：体力清理、材料获取等

- `timewindow`: 时间窗口执行 (如: `5-23` 表示5点到23点之间)- **BAAH 配置**：蔚蓝档案相关设置



### 任务定义配置详细配置说明请查看配置文件内的注释。



在 `[TaskDefinitions]` 部分定义任务执行步骤：## 🌐 Web 界面



```ini访问 `http://localhost:5000` 使用 Web 管理界面，提供以下功能：

[TaskDefinitions]

my_task = [- **任务监控**：实时查看任务运行状态

    {"type": "adb_wake", "params": [], "options": {"timeout": 10}},- **配置管理**：在线编辑配置文件

    {"type": "command", "params": ["echo", "Hello World"], "options": {"log": true}},- **日志查看**：浏览运行日志和错误信息

    {"type": "http_get", "params": ["http://example.com/api"], "options": {}},- **手动控制**：启动/停止特定任务

    {"type": "file_write", "params": ["output.txt", "Task completed"], "options": {}}

]## ⚠️ 安全注意事项

```

**重要警告**：本项目未实现用户认证机制，Web 界面可被任何能访问的用户控制。

## 🔧 支持的执行器类型

### 安全建议：

### ADB执行器1. **仅本地访问**：确保 Web 服务仅绑定到 localhost (127.0.0.1)

- `adb_wake`: 唤醒设备屏幕2. **防火墙保护**：不要在路由器或防火墙中开放相关端口

- `adb_start`: 启动应用3. **内网隔离**：如需局域网访问，确保网络环境安全

- `resolution`: 获取设备分辨率4. **VPN 访问**：远程管理请使用 VPN 连接后访问



### 命令执行器```bash

- `command`: 执行系统命令 (支持实时输出)# 检查服务绑定（推荐仅绑定本地）

- `wait`: 等待指定时间netstat -tlnp | grep :5000

```

### HTTP执行器

- `http_get`: HTTP GET请求## 📁 项目结构

- `http_post`: HTTP POST请求

- `webhook`: 发送WebHook通知```

MAA_Auto/

### 文件执行器├── maa_auto.py              # 主自动化脚本

- `file_write`: 写入文件├── web_manager.py           # Web 界面后端

- `file_read`: 读取文件├── config.example.ini       # 配置文件模板

- `file_copy`: 复制文件├── config.ini              # 实际配置文件（需自创建）

- `file_delete`: 删除文件├── maa-web-manager.service # systemd 服务文件

├── manage_web.sh           # Web 服务管理脚本

## 📈 监控功能├── test_web_manager.py     # Web 服务测试脚本

├── templates/              # Web 界面模板

### 关键词检测│   ├── base.html

│   ├── index.html

在 `[TaskKeywords]` 部分配置关键词检测：│   ├── config.html

│   ├── logs.html

```ini│   └── tasks.html

[TaskKeywords]└── logs/                   # 日志文件目录

my_task = {    ├── maa_auto.log

    "success": {    └── web_manager.log

        "keywords": ["完成", "成功", "success"],```

        "action": "webhook=success"

    },## 🔄 工作原理

    "error": {

        "keywords": ["错误", "失败", "error"],1. **时间窗口调度**：根据配置的时间窗口，系统自动在 MAA 和 BAAH 之间切换

        "action": "webhook=error"2. **智能监控**：监控游戏进程状态，自动处理异常情况

    }3. **任务队列**：按优先级执行日常任务、公招任务等

}4. **状态同步**：Web 界面实时显示当前运行状态和日志

```

## 🐛 故障排除

### WebHook通知

### 常见问题：

在 `[WebhookTemplates]` 部分配置通知模板：1. **ADB 连接失败**：检查模拟器状态和 ADB 配置

2. **MAA/BAAH 路径错误**：确认安装路径与配置文件一致

```ini3. **权限问题**：确保脚本有足够权限访问相关目录

[WebhookTemplates]4. **端口占用**：检查 5000 端口是否被其他服务占用

success = {

    "url": "${WEBHOOK_DINGDING_URL}",### 日志查看：

    "method": "POST",```bash

    "headers": {"Content-Type": "application/json"},# 查看主程序日志

    "data": {tail -f logs/maa_auto.log

        "msgtype": "text",

        "text": {"content": "任务执行成功: {{content}}"}# 查看 Web 服务日志

    }tail -f logs/web_manager.log

}```

```

## 🤝 开发环境

## 🛠️ 命令行工具

- **开发平台**：Orangepi5plus + Armbian

### 基本命令- **模拟器**：Redroid

- **测试环境**：Debian 12

```bash

# 查看任务状态## 📝 许可证

python main.py status

本项目遵循开源许可证，具体信息请查看 LICENSE 文件。

# 列出所有任务

python main.py list## 🔗 相关项目



# 添加新任务- [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights) - 《明日方舟》小助手

python main.py add task_name "interval|1h|1|0-60|default" '{"type": "command", "params": ["echo", "test"]}'- [BAAH](https://github.com/BlueArchiveArisHelper/BAAH) - 碧蓝档案爱丽丝助手



# 删除任务---

python main.py del task_name

```**注意**：本项目仅供学习交流使用，请遵守相关游戏的使用条款。


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
```

## 📁 日志管理

日志文件位置：
- 应用日志: `logs/maa_scheduler.log`
- 系统日志: `journalctl -u maa-scheduler`

日志级别可在 `task_config.ini` 中配置：
```ini
[SystemSettings]
log_level = INFO  # DEBUG, INFO, WARNING, ERROR
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
   - 查看日志文件排查错误

4. **WebHook通知失败**
   - 验证WebHook URL的有效性
   - 检查网络连接和防火墙设置

### 调试模式

启用详细日志：
```ini
[SystemSettings]
log_level = DEBUG
```

## 📄 许可证

MIT License

---

*MAA任务调度器 v1.0.0 - 让自动化更简单*