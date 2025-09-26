// MAA任务调度器 - 主要JavaScript文件

class MAAWebInterface {
    constructor() {
        this.currentLanguage = 'auto';
        this.currentTheme = 'auto';
        this.translations = {};
        this.init();
    }

    async init() {
        await this.loadTranslations();
        this.setupTheme();
        this.setupLanguage();
        this.setupEventListeners();
        this.loadInitialData();
    }

    // 翻译系统
    async loadTranslations() {
        // 中文翻译
        this.translations.zh = {
            // 导航
            'nav.dashboard': '仪表板',
            'nav.tasks': '任务管理',
            'nav.logs': '日志查看',
            'nav.settings': '系统设置',
            
            // 仪表板
            'dashboard.title': 'MAA任务调度器',
            'dashboard.scheduler_status': '调度器状态',
            'dashboard.total_tasks': '总任务数',
            'dashboard.active_tasks': '活跃任务',
            'dashboard.completed_tasks': '已完成',
            'dashboard.failed_tasks': '失败任务',
            'dashboard.uptime': '运行时间',
            
            // 任务状态
            'task.status.idle': '空闲',
            'task.status.running': '运行中',
            'task.status.completed': '已完成',
            'task.status.failed': '失败',
            'task.status.waiting': '等待中',
            
            // 任务操作
            'task.actions.start': '启动',
            'task.actions.stop': '停止',
            'task.actions.restart': '重启',
            'task.actions.view': '查看',
            'task.actions.edit': '编辑',
            'task.actions.delete': '删除',
            
            // 表格头
            'table.task_name': '任务名称',
            'table.status': '状态',
            'table.type': '类型',
            'table.priority': '优先级',
            'table.last_run': '最后运行',
            'table.next_run': '下次运行',
            'table.actions': '操作',
            
            // 按钮和控件
            'btn.refresh': '刷新',
            'btn.start_scheduler': '启动调度器',
            'btn.stop_scheduler': '停止调度器',
            'btn.clear_logs': '清空日志',
            'btn.export_logs': '导出日志',
            'btn.save': '保存',
            'btn.cancel': '取消',
            'btn.confirm': '确认',
            
            // 消息
            'msg.loading': '加载中...',
            'msg.no_data': '暂无数据',
            'msg.operation_success': '操作成功',
            'msg.operation_failed': '操作失败',
            'msg.confirm_delete': '确认删除此任务？',
            'msg.scheduler_started': '调度器已启动',
            'msg.scheduler_stopped': '调度器已停止',
            
            // 设置
            'settings.theme': '主题',
            'settings.language': '语言',
            'settings.theme.light': '浅色',
            'settings.theme.dark': '深色',
            'settings.theme.auto': '自动',
            'settings.language.zh': '中文',
            'settings.language.en': 'English',
            'settings.language.auto': '自动'
        };

        // 英文翻译
        this.translations.en = {
            // Navigation
            'nav.dashboard': 'Dashboard',
            'nav.tasks': 'Task Management',
            'nav.logs': 'Log Viewer',
            'nav.settings': 'Settings',
            
            // Dashboard
            'dashboard.title': 'MAA Task Scheduler',
            'dashboard.scheduler_status': 'Scheduler Status',
            'dashboard.total_tasks': 'Total Tasks',
            'dashboard.active_tasks': 'Active Tasks',
            'dashboard.completed_tasks': 'Completed',
            'dashboard.failed_tasks': 'Failed Tasks',
            'dashboard.uptime': 'Uptime',
            
            // Task Status
            'task.status.idle': 'Idle',
            'task.status.running': 'Running',
            'task.status.completed': 'Completed',
            'task.status.failed': 'Failed',
            'task.status.waiting': 'Waiting',
            
            // Task Actions
            'task.actions.start': 'Start',
            'task.actions.stop': 'Stop',
            'task.actions.restart': 'Restart',
            'task.actions.view': 'View',
            'task.actions.edit': 'Edit',
            'task.actions.delete': 'Delete',
            
            // Table Headers
            'table.task_name': 'Task Name',
            'table.status': 'Status',
            'table.type': 'Type',
            'table.priority': 'Priority',
            'table.last_run': 'Last Run',
            'table.next_run': 'Next Run',
            'table.actions': 'Actions',
            
            // Buttons and Controls
            'btn.refresh': 'Refresh',
            'btn.start_scheduler': 'Start Scheduler',
            'btn.stop_scheduler': 'Stop Scheduler',
            'btn.clear_logs': 'Clear Logs',
            'btn.export_logs': 'Export Logs',
            'btn.save': 'Save',
            'btn.cancel': 'Cancel',
            'btn.confirm': 'Confirm',
            
            // Messages
            'msg.loading': 'Loading...',
            'msg.no_data': 'No data available',
            'msg.operation_success': 'Operation successful',
            'msg.operation_failed': 'Operation failed',
            'msg.confirm_delete': 'Confirm to delete this task?',
            'msg.scheduler_started': 'Scheduler started',
            'msg.scheduler_stopped': 'Scheduler stopped',
            
            // Settings
            'settings.theme': 'Theme',
            'settings.language': 'Language',
            'settings.theme.light': 'Light',
            'settings.theme.dark': 'Dark',
            'settings.theme.auto': 'Auto',
            'settings.language.zh': '中文',
            'settings.language.en': 'English',
            'settings.language.auto': 'Auto'
        };
    }

    // 主题管理
    setupTheme() {
        // 从localStorage或API获取用户偏好
        const savedTheme = localStorage.getItem('theme') || 'auto';
        this.setTheme(savedTheme);
    }

    setTheme(theme) {
        this.currentTheme = theme;
        localStorage.setItem('theme', theme);

        if (theme === 'auto') {
            // 自动检测系统主题
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }

        // 更新主题切换按钮
        this.updateThemeButton();
        
        // 保存到服务器
        this.saveUserPreferences();
    }

    updateThemeButton() {
        const themeBtn = document.getElementById('theme-toggle');
        if (themeBtn) {
            const icons = {
                'light': '☀️',
                'dark': '🌙',
                'auto': '🔄'
            };
            themeBtn.innerHTML = icons[this.currentTheme] || icons['auto'];
            themeBtn.title = this.t(`settings.theme.${this.currentTheme}`);
        }
    }

    // 语言管理
    setupLanguage() {
        // 从localStorage或API获取用户偏好
        const savedLanguage = localStorage.getItem('language') || 'auto';
        this.setLanguage(savedLanguage);
    }

    setLanguage(language) {
        this.currentLanguage = language;
        localStorage.setItem('language', language);

        if (language === 'auto') {
            // 自动检测浏览器语言
            const browserLang = navigator.language || navigator.userLanguage;
            this.actualLanguage = browserLang.startsWith('zh') ? 'zh' : 'en';
        } else {
            this.actualLanguage = language;
        }

        // 更新页面文本
        this.updatePageText();
        
        // 更新语言切换按钮
        this.updateLanguageButton();
        
        // 保存到服务器
        this.saveUserPreferences();
    }

    updateLanguageButton() {
        const langBtn = document.getElementById('language-toggle');
        if (langBtn) {
            const labels = {
                'zh': '中',
                'en': 'EN',
                'auto': 'Auto'
            };
            langBtn.textContent = labels[this.currentLanguage] || labels['auto'];
        }
    }

    // 翻译函数
    t(key, params = {}) {
        const translation = this.translations[this.actualLanguage]?.[key] || key;
        
        // 简单的参数替换
        let result = translation;
        for (const [param, value] of Object.entries(params)) {
            result = result.replace(`{${param}}`, value);
        }
        
        return result;
    }

    // 更新页面文本
    updatePageText() {
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            element.textContent = this.t(key);
        });

        document.querySelectorAll('[data-i18n-title]').forEach(element => {
            const key = element.getAttribute('data-i18n-title');
            element.title = this.t(key);
        });

        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            element.placeholder = this.t(key);
        });
    }

    // 事件监听器
    setupEventListeners() {
        // 主题切换
        document.addEventListener('click', (e) => {
            if (e.target.id === 'theme-toggle') {
                const themes = ['light', 'dark', 'auto'];
                const currentIndex = themes.indexOf(this.currentTheme);
                const nextTheme = themes[(currentIndex + 1) % themes.length];
                this.setTheme(nextTheme);
            }
        });

        // 语言切换
        document.addEventListener('click', (e) => {
            if (e.target.id === 'language-toggle') {
                const languages = ['auto', 'zh', 'en'];
                const currentIndex = languages.indexOf(this.currentLanguage);
                const nextLanguage = languages[(currentIndex + 1) % languages.length];
                this.setLanguage(nextLanguage);
            }
        });

        // 系统主题变化监听
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (this.currentTheme === 'auto') {
                document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
            }
        });

        // 页面刷新按钮
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('refresh-btn')) {
                this.refreshData();
            }
        });
    }

    // 数据加载
    async loadInitialData() {
        await this.loadTasks();
        await this.loadSchedulerStatus();
        await this.loadLogs();
    }

    async loadTasks() {
        try {
            const response = await fetch('/api/tasks');
            const data = await response.json();
            
            if (data.success) {
                this.renderTasks(data.tasks);
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            this.showError('Failed to load tasks: ' + error.message);
        }
    }

    async loadSchedulerStatus() {
        try {
            const response = await fetch('/api/scheduler/status');
            const data = await response.json();
            
            if (data.success) {
                this.renderSchedulerStatus(data.status);
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            this.showError('Failed to load scheduler status: ' + error.message);
        }
    }

    async loadLogs() {
        try {
            const response = await fetch('/api/logs');
            const data = await response.json();
            
            if (data.success) {
                this.renderLogs(data.logs);
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            this.showError('Failed to load logs: ' + error.message);
        }
    }

    // 渲染函数
    renderTasks(tasks) {
        const container = document.getElementById('tasks-container');
        if (!container) return;

        if (tasks.length === 0) {
            container.innerHTML = `<div class="card"><div class="card-body text-center">${this.t('msg.no_data')}</div></div>`;
            return;
        }

        const html = tasks.map(task => `
            <div class="card" data-task="${task.name}">
                <div class="card-header">
                    <h5>${task.name}</h5>
                    <span class="badge badge-${this.getStatusColor(task.status)}">${this.t('task.status.' + task.status)}</span>
                </div>
                <div class="card-body">
                    <p><strong>${this.t('table.type')}:</strong> ${task.type}</p>
                    <p><strong>${this.t('table.priority')}:</strong> ${task.priority}</p>
                    <p><strong>Payloads:</strong> ${task.payload_count}</p>
                </div>
                <div class="card-footer">
                    <button class="btn btn-sm btn-primary" onclick="app.viewTask('${task.name}')">${this.t('task.actions.view')}</button>
                    <button class="btn btn-sm btn-success" onclick="app.startTask('${task.name}')">${this.t('task.actions.start')}</button>
                    <button class="btn btn-sm btn-warning" onclick="app.stopTask('${task.name}')">${this.t('task.actions.stop')}</button>
                </div>
            </div>
        `).join('');

        container.innerHTML = html;
    }

    renderSchedulerStatus(status) {
        const container = document.getElementById('scheduler-status');
        if (!container) return;

        const html = `
            <div class="card">
                <div class="card-header">
                    <h5>${this.t('dashboard.scheduler_status')}</h5>
                    <span class="badge badge-${status.running ? 'success' : 'danger'}">${status.running ? 'Running' : 'Stopped'}</span>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-3">
                            <h6>${this.t('dashboard.total_tasks')}</h6>
                            <h4>${status.total_tasks}</h4>
                        </div>
                        <div class="col-md-3">
                            <h6>${this.t('dashboard.active_tasks')}</h6>
                            <h4>${status.active_tasks}</h4>
                        </div>
                        <div class="col-md-3">
                            <h6>${this.t('dashboard.completed_tasks')}</h6>
                            <h4>${status.completed_tasks}</h4>
                        </div>
                        <div class="col-md-3">
                            <h6>${this.t('dashboard.failed_tasks')}</h6>
                            <h4>${status.failed_tasks}</h4>
                        </div>
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    renderLogs(logs) {
        const container = document.getElementById('logs-container');
        if (!container) return;

        if (logs.length === 0) {
            container.innerHTML = `<div class="log-line">${this.t('msg.no_data')}</div>`;
            return;
        }

        const html = logs.map(log => `
            <div class="log-line">
                <span class="log-timestamp">${new Date(log.timestamp).toLocaleString()}</span>
                <span class="log-message">${log.message}</span>
            </div>
        `).join('');

        container.innerHTML = html;
        
        // 滚动到底部
        container.scrollTop = container.scrollHeight;
    }

    // 工具函数
    getStatusColor(status) {
        const colors = {
            'idle': 'secondary',
            'running': 'primary',
            'completed': 'success',
            'failed': 'danger',
            'waiting': 'warning'
        };
        return colors[status] || 'secondary';
    }

    showError(message) {
        console.error(message);
        // TODO: 显示错误通知
    }

    showSuccess(message) {
        console.log(message);
        // TODO: 显示成功通知
    }

    // 任务操作
    async viewTask(taskName) {
        try {
            const response = await fetch(`/api/task/${taskName}`);
            const data = await response.json();
            
            if (data.success) {
                // TODO: 显示任务详情模态框
                console.log('Task details:', data.task);
            } else {
                this.showError(data.error);
            }
        } catch (error) {
            this.showError('Failed to load task details: ' + error.message);
        }
    }

    async startTask(taskName) {
        // TODO: 实现任务启动
        this.showSuccess(`Task ${taskName} started`);
    }

    async stopTask(taskName) {
        // TODO: 实现任务停止
        this.showSuccess(`Task ${taskName} stopped`);
    }

    async refreshData() {
        await this.loadInitialData();
        this.showSuccess(this.t('msg.operation_success'));
    }

    // 用户偏好保存
    async saveUserPreferences() {
        try {
            await fetch('/api/user/preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    theme: this.currentTheme,
                    language: this.currentLanguage
                })
            });
        } catch (error) {
            console.error('Failed to save user preferences:', error);
        }
    }
}

// 全局初始化
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new MAAWebInterface();
});