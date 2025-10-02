(function (window) {
  const dictionaries = {
    zh: {
      'app.name': 'MAA 调度器',
      'header.toggleSidebar': '菜单',
      'header.language': '语言',
      'language.zh': '中文',
      'language.en': 'English',
      'language.label': '选择语言',
      'nav.dashboard': '仪表板',
      'nav.tasks': '任务管理',
      'nav.monitor': '实时监控',
      'nav.logs': '日志查看',
      'nav.settings': '系统设置',
      'system.status': '系统状态',
      'system.running': '运行状态',
      'system.mode': '模式',
      'system.taskCount': '任务数',
      'system.runningTasks': '运行中',
      'system.running.true': '运行中',
      'system.running.false': '已停止',
      'system.mode.auto': '自动调度',
      'system.mode.single': '单任务模式',
      'system.mode.label': '调度模式',
      'action.refresh': '刷新',
      'action.startScheduler': '启动调度器',
      'action.stopScheduler': '停止调度器',
      'action.search': '搜索',
      'action.create': '新建',
      'action.save': '保存',
      'action.close': '关闭',
      'action.run': '立即执行',
      'action.cancel': '取消任务',
      'action.delete': '删除任务',
      'action.confirm': '确定',
      'confirm.stopScheduler': '确定要停止调度器吗？这将取消所有正在运行的任务。',
      'dashboard.title': '仪表板',
      'dashboard.cards.total': '总任务数',
      'dashboard.cards.running': '运行中任务',
      'dashboard.cards.queued': '队列中任务',
      'dashboard.cards.scheduled': '定时任务',
      'dashboard.resourceGroupTitle': '资源分组状态',
      'dashboard.runningTasksTitle': '正在运行的任务',
      'dashboard.runningEmpty': '暂无运行中的任务',
      'dashboard.recentTasksTitle': '最近完成的任务',
      'dashboard.recentEmpty': '暂无完成的任务',
      'dashboard.refresh': '刷新',
    'dashboard.origin.scheduler': '自动调度',
    'dashboard.origin.manual': '手动执行',
    'dashboard.origin.retry': '失败重试',
    'dashboard.origin.successRetry': '时间段重复执行',
    'dashboard.retryAttemptLabel': '第 {value} 次尝试',
    'dashboard.successRetryAttemptLabel': '窗口内第 {value} 次',
    'dashboard.triggerType.scheduled': '定时',
    'dashboard.triggerType.interval': '间隔',
    'dashboard.triggerType.random_time': '随机',
    'dashboard.triggerType.weekly': '每周',
    'dashboard.triggerType.monthly': '每月',
    'dashboard.triggerType.specific_date': '指定日期',
    'dashboard.triggerType.manual': '手动',
  'dashboard.durationSeconds': '{value} 秒',
  'dashboard.group.usage': '{running} / {max} 正在使用',
  'dashboard.group.available': '可用: {available}',
  'dashboard.group.runningTasks': '运行中: {tasks}',
  'dashboard.group.idle': '空闲',
      'status.pending': '待执行',
      'status.running': '执行中',
      'status.completed': '已完成',
      'status.failed': '失败',
      'status.cancelled': '已取消',
      'status.preempted': '已抢占',
  'status.loading': '加载中',
  'error.requestFailed': '请求失败',
  'toast.scheduler.started': '调度器启动成功',
  'toast.scheduler.stopped': '调度器已停止',
  'toast.scheduler.modeChanged': '已切换到 {mode} 模式',
      'tasks.toast.manualRunBlocked': '请先停止调度器或切换到单任务模式后再手动执行任务',
      'tasks.title': '任务管理',
      'tasks.create': '新建任务',
      'tasks.refresh': '刷新',
      'tasks.searchPlaceholder': '搜索任务名称或描述...',
      'tasks.statusFilter': '所有状态',
      'tasks.groupFilter': '所有资源分组',
      'tasks.clearFilters': '清除筛选',
      'tasks.table.loading': '正在加载任务...',
      'tasks.table.headers.name': '任务名称',
      'tasks.table.headers.status': '状态',
      'tasks.table.headers.priority': '优先级',
      'tasks.table.headers.group': '资源分组',
      'tasks.table.headers.trigger': '触发类型',
      'tasks.table.headers.next': '下次执行',
      'tasks.table.headers.actions': '操作',
      'tasks.form.retry.success': '成功后在时间窗口内继续运行',
      'tasks.form.retry.successHint': '仅适用于定时触发的任务，用于在时间段内多次执行。',
      'tasks.form.retry.successDelay': '成功重试延迟（秒）',
      'tasks.form.retry.successDelayPlaceholder': '默认同失败重试延迟',
      'tasks.form.retry.successMax': '成功重试次数上限',
      'tasks.form.retry.successMaxHint': '用于限制同一时间窗口内的额外执行次数。',
      'monitor.title': '实时监控',
      'monitor.refresh': '刷新',
      'monitor.autoRefresh.pause': '暂停自动刷新',
      'monitor.autoRefresh.resume': '恢复自动刷新',
      'monitor.runningEmpty': '暂无运行中的任务',
      'settings.title': '系统设置'
    },
    en: {
      'app.name': 'MAA Scheduler',
      'header.toggleSidebar': 'Menu',
      'header.language': 'Language',
      'language.zh': '中文',
      'language.en': 'English',
      'language.label': 'Language',
      'nav.dashboard': 'Dashboard',
      'nav.tasks': 'Tasks',
      'nav.monitor': 'Monitor',
      'nav.logs': 'Logs',
      'nav.settings': 'Settings',
      'system.status': 'System Status',
      'system.running': 'Status',
      'system.mode': 'Mode',
      'system.taskCount': 'Tasks',
      'system.runningTasks': 'Running',
      'system.running.true': 'Running',
      'system.running.false': 'Stopped',
      'system.mode.auto': 'Auto Scheduling',
      'system.mode.single': 'Single Task Mode',
      'system.mode.label': 'Scheduler Mode',
      'action.refresh': 'Refresh',
      'action.startScheduler': 'Start Scheduler',
      'action.stopScheduler': 'Stop Scheduler',
      'action.search': 'Search',
      'action.create': 'Create',
      'action.save': 'Save',
      'action.close': 'Close',
      'action.run': 'Run Now',
      'action.cancel': 'Cancel Task',
      'action.delete': 'Delete Task',
      'action.confirm': 'Confirm',
      'confirm.stopScheduler': 'Stop the scheduler? This will cancel all running tasks.',
      'dashboard.title': 'Dashboard',
      'dashboard.cards.total': 'Total Tasks',
      'dashboard.cards.running': 'Running Tasks',
      'dashboard.cards.queued': 'Queued Tasks',
      'dashboard.cards.scheduled': 'Scheduled Jobs',
      'dashboard.resourceGroupTitle': 'Resource Groups',
      'dashboard.runningTasksTitle': 'Running Tasks',
      'dashboard.runningEmpty': 'No tasks are running',
      'dashboard.recentTasksTitle': 'Recent Completions',
      'dashboard.recentEmpty': 'No completed tasks yet',
      'dashboard.refresh': 'Refresh',
    'dashboard.origin.scheduler': 'Scheduled',
    'dashboard.origin.manual': 'Manual Run',
    'dashboard.origin.retry': 'Auto Retry',
    'dashboard.origin.successRetry': 'Window Repeat',
    'dashboard.retryAttemptLabel': 'Attempt #{value}',
    'dashboard.successRetryAttemptLabel': 'Window run #{value}',
    'dashboard.triggerType.scheduled': 'Scheduled',
    'dashboard.triggerType.interval': 'Interval',
    'dashboard.triggerType.random_time': 'Random',
    'dashboard.triggerType.weekly': 'Weekly',
    'dashboard.triggerType.monthly': 'Monthly',
    'dashboard.triggerType.specific_date': 'Specific Date',
    'dashboard.triggerType.manual': 'Manual',
  'dashboard.durationSeconds': '{value}s',
  'dashboard.group.usage': '{running} / {max} in use',
  'dashboard.group.available': 'Available: {available}',
  'dashboard.group.runningTasks': 'Running: {tasks}',
  'dashboard.group.idle': 'Idle',
      'status.pending': 'Pending',
      'status.running': 'Running',
      'status.completed': 'Completed',
      'status.failed': 'Failed',
      'status.cancelled': 'Cancelled',
      'status.preempted': 'Preempted',
  'status.loading': 'Loading',
  'error.requestFailed': 'Request failed',
  'toast.scheduler.started': 'Scheduler started',
  'toast.scheduler.stopped': 'Scheduler stopped',
  'toast.scheduler.modeChanged': 'Switched to {mode}',
      'tasks.toast.manualRunBlocked': 'Stop the scheduler or switch to single-task mode before manual execution',
      'tasks.title': 'Tasks',
      'tasks.create': 'New Task',
      'tasks.refresh': 'Refresh',
      'tasks.searchPlaceholder': 'Search by name or description...',
      'tasks.statusFilter': 'All statuses',
      'tasks.groupFilter': 'All groups',
      'tasks.clearFilters': 'Clear filters',
      'tasks.table.loading': 'Loading tasks...',
      'tasks.table.headers.name': 'Task Name',
      'tasks.table.headers.status': 'Status',
      'tasks.table.headers.priority': 'Priority',
      'tasks.table.headers.group': 'Resource Group',
      'tasks.table.headers.trigger': 'Trigger Type',
      'tasks.table.headers.next': 'Next Run',
      'tasks.table.headers.actions': 'Actions',
      'tasks.form.retry.success': 'Continue within time window after success',
      'tasks.form.retry.successHint': 'Only applies to scheduled triggers and allows multiple runs within the window.',
      'tasks.form.retry.successDelay': 'Success retry delay (seconds)',
      'tasks.form.retry.successDelayPlaceholder': 'Default: failure retry delay',
      'tasks.form.retry.successMax': 'Success retry limit',
      'tasks.form.retry.successMaxHint': 'Limits extra executions within the same time window.',
      'monitor.title': 'Live Monitor',
      'monitor.refresh': 'Refresh',
      'monitor.autoRefresh.pause': 'Pause auto refresh',
      'monitor.autoRefresh.resume': 'Resume auto refresh',
      'monitor.runningEmpty': 'No running tasks',
      'settings.title': 'Settings'
    }
  };

  const SUPPORTED_ATTRS = ['placeholder', 'title', 'aria-label'];

  const AppI18n = {
    dictionaries,
    storageKey: 'maa_lang',
    defaultLang: 'zh',
    current: 'zh',
    pageTitleKey: null,

    init() {
      try {
        const stored = window.localStorage.getItem(this.storageKey);
        if (stored && this.dictionaries[stored]) {
          this.current = stored;
        } else {
          const browserLang = (navigator.language || navigator.userLanguage || 'zh').toLowerCase();
          this.current = browserLang.startsWith('zh') ? 'zh' : 'en';
        }
      } catch (err) {
        console.warn('无法读取语言设置，将使用默认语言', err);
        this.current = this.defaultLang;
      }

      this._applyDocumentLang();
      this.apply();
    },

    setLanguage(lang, persist = true) {
      if (!this.dictionaries[lang]) {
        lang = this.defaultLang;
      }
      this.current = lang;
      if (persist) {
        try {
          window.localStorage.setItem(this.storageKey, lang);
        } catch (err) {
          console.warn('无法保存语言设置', err);
        }
      }
      this._applyDocumentLang();
      this.apply();
    },

    _applyDocumentLang() {
      document.documentElement.setAttribute('lang', this.current === 'zh' ? 'zh-CN' : 'en');
      this._applyTitle();
    },

    apply(scope = document) {
      const elements = scope.querySelectorAll('[data-i18n]');
      elements.forEach((el) => {
        const key = el.getAttribute('data-i18n');
        const fallback = el.getAttribute('data-i18n-default') || el.textContent.trim();
        const value = this.t(key, fallback);
        if (value !== null && value !== undefined) {
          el.textContent = value;
        }
      });

      SUPPORTED_ATTRS.forEach((attr) => {
        const attrSelector = `[data-i18n-${attr}]`;
        scope.querySelectorAll(attrSelector).forEach((el) => {
          const key = el.getAttribute(`data-i18n-${attr}`);
          const fallback = el.getAttribute(attr) || '';
          const value = this.t(key, fallback);
          if (value !== null && value !== undefined) {
            el.setAttribute(attr, value);
          }
        });
      });

      this._applyTitle();
    },

    registerPageTitle(key) {
      this.pageTitleKey = key;
      this._applyTitle();
    },

    _applyTitle() {
      if (!this.pageTitleKey) {
        return;
      }
      const title = this.t(this.pageTitleKey, document.title);
      if (title) {
        document.title = title;
      }
    },

    bindLanguageSelector(selectEl) {
      if (!selectEl) {
        return;
      }
      selectEl.value = this.current;
      selectEl.addEventListener('change', (event) => {
        this.setLanguage(event.target.value);
      });
    },

    t(key, fallback = null) {
      if (!key) {
        return fallback;
      }
      const table = this.dictionaries[this.current] || {};
      if (Object.prototype.hasOwnProperty.call(table, key)) {
        return table[key];
      }
      const defaultTable = this.dictionaries[this.defaultLang] || {};
      if (Object.prototype.hasOwnProperty.call(defaultTable, key)) {
        return defaultTable[key];
      }
      return fallback !== null ? fallback : key;
    },

    statusText(status) {
      if (!status) {
        return '';
      }
      const normalized = String(status).toLowerCase();
      return this.t(`status.${normalized}`, normalized);
    },

    getLanguage() {
      return this.current;
    }
  };

  window.AppI18n = AppI18n;
})(window);
