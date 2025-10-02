# MAA/BAAH Task Scheduler

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-managed-36393f?logo=astral&logoColor=white)](https://github.com/astral-sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

[:cn: 中文说明](README.md)  The English description is translated from the Chinese description, and may not be accurate or up-to-date.

> A systemd-friendly scheduler for command line automation tasks.

The project started as a helper for MAA automation and now supports BAAH along with any other deployable terminal program. You can configure multiple scripts with the same queue, trigger, and monitoring workflow, all managed through a web UI.

## Features

### Core capabilities
- **Flexible triggers**: Cron-like schedules, interval runs, random time windows, weekly and monthly events.
- **Resource groups**: Avoid hardware contention and limit concurrency per group.
- **Priority queue**: Deterministic ordering with manual overrides when needed.
- **Retry policies**: Configure failure retries and optional success retries inside time windows.
- **Live monitoring**: Dashboard shows running jobs, history, and group usage.
- **Log handling**: Shared log plus per-task buffers with keyword alerts.
- **Notification hooks**: Webhook integration for task status updates.
- **Mode switching**: Toggle between automated scheduling and single-task/manual mode.
- **Extensible task types**: Register any CLI/script task, including MAA, BAAH, or custom tooling.

### Web experience
- Task management: create, edit, clone, delete, and run jobs.
- Status board: running tasks, recent history, resource summary.
- Log viewer: fetch live or archived logs for each task.
- Settings panel: update scheduler behaviour and webhook credentials.

## Getting started

### 1. Prerequisites

Make sure Python 3.9+ and `uv` are installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Project setup

1. Clone the repository and enter the folder:
   ```bash
   cd /Task/MAA_Auto
   ```
2. Configure environment variables in `.env` (optional webhook integration):
   ```env
   WEBHOOK_UID=your_uid
   WEBHOOK_TOKEN=your_token
   WEBHOOK_BASE_URL=https://your_uid.push.ft07.com/send/your_token.send
   ```
3. Edit `config/tasks.yaml` to describe your jobs:
   - Keep the original MAA tasks if you still need them.
   - Add BAAH or other programs by specifying the command, parameters, and trigger type.
   - All tasks can reuse the same retry and notification policies.

### 3. Install dependencies

```bash
uv sync
```

### 4. Validate configuration

```bash
uv run python -m src.maa_scheduler.main check-config
```

### 5. Run the services

```bash
# Scheduler + Web UI
uv run python -m src.maa_scheduler.main main

# Scheduler only
uv run python -m src.maa_scheduler.main start

# Web UI only
uv run python -m src.maa_scheduler.main web
```

Visit the dashboard at <http://localhost:8080>.

# Command line reference

```bash
# Help
uv run python -m src.maa_scheduler.main --help

# List tasks
uv run python -m src.maa_scheduler.main list-tasks

# Check configuration
uv run python -m src.maa_scheduler.main check-config

# Send a test notification
uv run python -m src.maa_scheduler.main test notification
```

## Systemd integration

A ready-to-edit unit file lives in `config/systemd/maa-scheduler.service`.

1. Copy it into place:
   ```bash
   sudo cp config/systemd/maa-scheduler.service /etc/systemd/system/maa-scheduler.service
   sudo chown root:root /etc/systemd/system/maa-scheduler.service
   ```
2. Adjust user, working directory, and the path to `uv`:
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
3. Reload and enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable maa-scheduler.service
   sudo systemctl start maa-scheduler.service
   ```
4. Check status with `sudo systemctl status maa-scheduler.service`.

## API overview

- `GET /api/status` – Scheduler status and queue size.
- `POST /api/scheduler/start` – Start scheduling.
- `POST /api/scheduler/stop` – Stop scheduling.
- `POST /api/scheduler/mode` – Switch between modes.
- `GET /api/tasks` – List tasks.
- `POST /api/tasks` – Create a task.
- `GET /api/tasks/{task_id}` – Fetch task details.
- `PUT /api/tasks/{task_id}` – Update a task.
- `DELETE /api/tasks/{task_id}` – Remove a task.
- `POST /api/tasks/{task_id}/run` – Manual execution.
- `POST /api/tasks/{task_id}/cancel` – Cancel a running task.
- `GET /api/logs` – Read system log excerpts.
- `GET /api/tasks/{task_id}/logs` – Retrieve individual task logs.

## Troubleshooting

1. **Task never runs**
   - Check resource group configuration and concurrent limits.
   - Confirm the scheduler is in automatic mode.
   - Inspect task logs via the web UI.

2. **Notifications fail**
   - Verify webhook credentials.
   - Ensure outbound network access.
   - Use the built-in notification test.

3. **Web UI unavailable**
   - Make sure the port is open.
   - Review firewall rules.
   - Inspect logs in `logs/maa_scheduler.log`.

## Project layout

```
src/maa_scheduler/
├── __init__.py        # Package init
├── main.py            # Entry points
├── config.py          # Configuration handling
├── scheduler.py       # Scheduling logic
├── executor.py        # Execution engine
├── notification.py    # Notification layer
├── web_ui.py          # FastAPI + templates
└── templates/
    ├── base.html
    ├── index.html
    └── tasks.html
```

## Development

```bash
# Install dev extras
uv sync --dev

# Run tests
uv run pytest

# Formatting
uv run black src/
uv run flake8 src/
```

## License

This project is released under the MIT License. See [LICENSE](./LICENSE) for details.
