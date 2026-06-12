// 爱通知小爱音箱消息推送统一API平台 - 主JavaScript文件

// 全局应用对象
const App = {
    // 配置
    config: {
        apiBaseUrl: '/api/v1',
        version: '2.0.0'
    },
    
    // 状态管理
    state: {
        user: null,
        devices: [],
        apiKeys: [],
        miAccounts: [],
        currentTheme: 'light'
    },
    
    // 初始化应用
    init() {
        this.setupEventListeners();
        this.loadTheme();
        this.checkAuthStatus();
        this.setupSidebar();
    },
    
    // 设置事件监听器
    setupEventListeners() {
        // 主题切换
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
        
        // 侧边栏切换 (移动端)
        const sidebarToggle = document.getElementById('sidebar-toggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        }
        
        // 模态框关闭
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeModal(e.target);
            }
        });
        
        // 表单提交
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.dataset.ajaxForm !== undefined) {
                e.preventDefault();
                this.handleFormSubmit(form);
            }
        });
        
        // 复制功能
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('copy-btn') || e.target.closest('.copy-btn')) {
                e.preventDefault();
                const btn = e.target.classList.contains('copy-btn') ? e.target : e.target.closest('.copy-btn');
                this.copyToClipboard(btn.dataset.copy);
            }
        });
    },
    
    // 主题管理
    loadTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        this.setTheme(savedTheme);
    },
    
    setTheme(theme) {
        this.state.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        const themeIcon = document.querySelector('#theme-toggle i');
        if (themeIcon) {
            themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    },
    
    toggleTheme() {
        const newTheme = this.state.currentTheme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    },
    
    // 导航栏管理
    setupSidebar() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.navbar-link');
        
        navLinks.forEach(link => {
            link.classList.remove('active');
            const href = link.getAttribute('href');
            if (href && (currentPath.endsWith(href) || currentPath.includes(href.replace('.html', '')))) {
                link.classList.add('active');
            }
        });
    },
    
    toggleSidebar() {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.toggle('active');
        }
    },
    
    // 认证管理
    async checkAuthStatus() {
        try {
            const token = localStorage.getItem('auth_token');
            if (!token) {
                this.redirectToLogin();
                return;
            }
            
            // /auth/verify端点直接返回用户信息，不包含success字段
            const user = await this.apiCall('/auth/verify', 'POST', {}, token);
            this.state.user = user;
            this.updateUserDisplay();
        } catch (error) {
            console.error('认证检查失败:', error);
            // 认证失败，清除无效token并重定向
            localStorage.removeItem('auth_token');
            this.state.user = null;
            this.redirectToLogin();
        }
    },

    redirectToLogin() {
        // 只在非认证页面时重定向
        if (!window.location.pathname.includes('login') && 
            !window.location.pathname.includes('register') &&
            !window.location.pathname.includes('index')) {
            // 清除可能的无效状态
            this.state.user = null;
            window.location.href = '/login';
        }
    },
    
    updateUserDisplay() {
        const userDisplay = document.getElementById('user-display');
        if (userDisplay && this.state.user) {
            userDisplay.textContent = this.state.user.display_name || this.state.user.username;
        }
    },
    
    async logout() {
        try {
            await this.apiCall('/auth/logout', 'POST');
        } catch (error) {
            console.error('登出请求失败:', error);
        }
        
        localStorage.removeItem('auth_token');
        window.location.href = '/index.html';
    },
    
    // API调用
    async apiCall(endpoint, method = 'GET', data = null, token = null) {
        const url = `${this.config.apiBaseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        } else {
            const authToken = localStorage.getItem('auth_token');
            if (authToken) {
                headers['Authorization'] = `Bearer ${authToken}`;
            }
        }
        
        const options = {
            method,
            headers
        };
        
        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    },
    
    // 表单处理
    async handleFormSubmit(form) {
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        
        // 显示加载状态
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading"></span> 处理中...';
        
        try {
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            const endpoint = form.dataset.endpoint;
            const method = form.dataset.method || 'POST';
            
            const response = await this.apiCall(endpoint, method, data);
            
            if (response.success) {
                this.showAlert('success', response.message || '操作成功');
                
                // 处理特定表单的成功回调
                const onSuccess = form.dataset.onSuccess;
                if (onSuccess && typeof window[onSuccess] === 'function') {
                    window[onSuccess](response);
                }
            } else {
                this.showAlert('danger', response.message || '操作失败');
            }
        } catch (error) {
            console.error('表单提交失败:', error);
            this.showAlert('danger', '网络错误，请稍后重试');
        } finally {
            // 恢复按钮状态
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    },
    
    // 模态框管理
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    },
    
    closeModal(modal) {
        if (typeof modal === 'string') {
            modal = document.getElementById(modal);
        }
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    },
    
    // 通知和警告
    showAlert(type, message, duration = 5000) {
        const alertContainer = document.getElementById('alert-container') || this.createAlertContainer();
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span>${message}</span>
                <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        
        alertContainer.appendChild(alert);
        
        // 自动移除
        if (duration > 0) {
            setTimeout(() => {
                if (alert.parentElement) {
                    alert.remove();
                }
            }, duration);
        }
    },
    
    createAlertContainer() {
        const container = document.createElement('div');
        container.id = 'alert-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 3000;
            max-width: 400px;
        `;
        document.body.appendChild(container);
        return container;
    },
    
    // 复制到剪贴板
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showAlert('success', '已复制到剪贴板', 2000);
        } catch (error) {
            console.error('复制失败:', error);
            // 降级到旧方法
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                this.showAlert('success', '已复制到剪贴板', 2000);
            } catch (err) {
                this.showAlert('danger', '复制失败');
            }
            document.body.removeChild(textArea);
        }
    },
    
    // 格式化日期
    formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleString('zh-CN');
    },
    
    // 格式化文件大小
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    // 防抖函数
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // 节流函数
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    }
};

// 页面特定功能
const PageModules = {
    // 设备管理页面
    devices: {
        async loadDevices() {
            try {
                const response = await App.apiCall('/devices');
                if (response.success) {
                    App.state.devices = response.devices;
                    this.renderDeviceList();
                }
            } catch (error) {
                console.error('加载设备失败:', error);
                App.showAlert('danger', '加载设备列表失败');
            }
        },
        
        renderDeviceList() {
            const container = document.getElementById('device-list');
            if (!container) return;
            
            const html = App.state.devices.map(device => `
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h5 class="mb-sm">${device.device_name}</h5>
                                <p class="text-muted mb-sm">ID: ${device.device_id}</p>
                                <p class="text-muted mb-sm">型号: ${device.device_model}</p>
                                <span class="status status-${device.device_status === 'online' ? 'online' : 'offline'}">
                                    <span class="status-dot"></span>
                                    ${device.device_status === 'online' ? '在线' : '离线'}
                                </span>
                            </div>
                            <div class="d-flex flex-column gap-sm">
                                <button class="btn btn-sm btn-outline copy-btn" data-copy="${device.device_id}">
                                    <i class="fas fa-copy"></i> 复制ID
                                </button>
                                <button class="btn btn-sm btn-outline copy-btn" data-copy="${device.device_name}">
                                    <i class="fas fa-copy"></i> 复制名称
                                </button>
                                <button class="btn btn-sm btn-primary" onclick="PageModules.devices.testDevice('${device.device_id}')">
                                    <i class="fas fa-volume-up"></i> 测试
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
            
            container.innerHTML = html;
        },
        
        async testDevice(deviceId) {
            try {
                const response = await App.apiCall('/speak', 'POST', {
                    text: '设备测试，语音播放正常',
                    device_id: deviceId
                });
                
                if (response.success) {
                    App.showAlert('success', '测试语音已发送');
                }
            } catch (error) {
                console.error('设备测试失败:', error);
                App.showAlert('danger', '设备测试失败');
            }
        }
    },
    
    // API密钥管理页面
    apiKeys: {
        async loadApiKeys() {
            try {
                const response = await App.apiCall('/api-keys');
                if (response.success) {
                    App.state.apiKeys = response.api_keys;
                    this.renderApiKeyList();
                }
            } catch (error) {
                console.error('加载API密钥失败:', error);
                App.showAlert('danger', '加载API密钥失败');
            }
        },
        
        renderApiKeyList() {
            const container = document.getElementById('apikey-list');
            if (!container) return;
            
            const html = App.state.apiKeys.map(key => `
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h5 class="mb-sm">${key.key_name}</h5>
                                <p class="text-muted mb-sm">
                                    <span class="status status-${key.is_active ? 'online' : 'offline'}">
                                        <span class="status-dot"></span>
                                        ${key.is_active ? '启用' : '禁用'}
                                    </span>
                                </p>
                                <p class="text-muted mb-sm">使用次数: ${key.usage_count}</p>
                                <p class="text-muted">最后使用: ${App.formatDate(key.last_used)}</p>
                            </div>
                            <div class="d-flex flex-column gap-sm">
                                <button class="btn btn-sm btn-outline copy-btn" data-copy="${key.api_key}">
                                    <i class="fas fa-copy"></i> 复制密钥
                                </button>
                                <button class="btn btn-sm btn-secondary" onclick="PageModules.apiKeys.editKey(${key.id})">
                                    <i class="fas fa-edit"></i> 编辑
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="PageModules.apiKeys.deleteKey(${key.id})">
                                    <i class="fas fa-trash"></i> 删除
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
            
            container.innerHTML = html;
        },
        
        async createKey(formData) {
            try {
                const response = await App.apiCall('/api-keys', 'POST', formData);
                if (response.success) {
                    App.showAlert('success', 'API密钥创建成功');
                    App.closeModal('create-key-modal');
                    this.loadApiKeys();
                }
            } catch (error) {
                console.error('创建API密钥失败:', error);
                App.showAlert('danger', '创建API密钥失败');
            }
        },
        
        async deleteKey(keyId) {
            if (!confirm('确定要删除这个API密钥吗？此操作不可恢复。')) {
                return;
            }
            
            try {
                const response = await App.apiCall(`/api-keys/${keyId}`, 'DELETE');
                if (response.success) {
                    App.showAlert('success', 'API密钥已删除');
                    this.loadApiKeys();
                }
            } catch (error) {
                console.error('删除API密钥失败:', error);
                App.showAlert('danger', '删除API密钥失败');
            }
        }
    },
    
    // 小米账户管理页面
    miAccounts: {
        async loadMiAccounts() {
            try {
                const response = await App.apiCall('/mi-accounts');
                if (response.success) {
                    App.state.miAccounts = response.accounts;
                    this.renderMiAccountList();
                }
            } catch (error) {
                console.error('加载小米账户失败:', error);
                App.showAlert('danger', '加载小米账户失败');
            }
        },
        
        renderMiAccountList() {
            const container = document.getElementById('mi-account-list');
            if (!container) return;
            
            const html = App.state.miAccounts.map(account => `
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h5 class="mb-sm">${account.mi_username}</h5>
                                <p class="text-muted mb-sm">
                                    <span class="status status-${account.is_active ? 'online' : 'offline'}">
                                        <span class="status-dot"></span>
                                        ${account.is_active ? '已连接' : '连接失败'}
                                    </span>
                                </p>
                                <p class="text-muted">最后同步: ${App.formatDate(account.last_sync)}</p>
                            </div>
                            <div class="d-flex flex-column gap-sm">
                                <button class="btn btn-sm btn-primary" onclick="PageModules.miAccounts.syncAccount(${account.id})">
                                    <i class="fas fa-sync"></i> 同步设备
                                </button>
                                <button class="btn btn-sm btn-secondary" onclick="PageModules.miAccounts.testAccount(${account.id})">
                                    <i class="fas fa-test-tube"></i> 测试连接
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="PageModules.miAccounts.deleteAccount(${account.id})">
                                    <i class="fas fa-trash"></i> 删除
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('');
            
            container.innerHTML = html;
        },
        
        async syncAccount(accountId) {
            try {
                const response = await App.apiCall(`/mi-accounts/${accountId}/sync`, 'POST');
                if (response.success) {
                    App.showAlert('success', '设备同步成功');
                    this.loadMiAccounts();
                }
            } catch (error) {
                console.error('同步失败:', error);
                App.showAlert('danger', '设备同步失败');
            }
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    App.init();
    
    // 根据页面加载对应模块
    const page = document.body.dataset.page;
    if (page && PageModules[page]) {
        // 延迟加载，确保认证检查完成
        setTimeout(() => {
            if (PageModules[page].init) {
                PageModules[page].init();
            }
        }, 100);
    }
});

// 全局错误处理
window.addEventListener('error', (e) => {
    console.error('全局错误:', e.error);
    App.showAlert('danger', '发生了一个错误，请刷新页面重试');
});

// 导出到全局作用域
window.App = App;
window.PageModules = PageModules;
