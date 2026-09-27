/**
 * 爱通知小爱音箱消息推送统一API平台 - 前端API客户端
 */

class ApiClient {
    constructor(baseURL = '/api/v1') {
        this.baseURL = baseURL;
        this.token = this.getToken();
    }

    /**
     * 获取存储的认证令牌
     */
    getToken() {
        return localStorage.getItem('auth_token');
    }

    /**
     * 设置认证令牌
     */
    setToken(token) {
        if (token) {
            localStorage.setItem('auth_token', token);
            this.token = token;
        } else {
            localStorage.removeItem('auth_token');
            this.token = null;
        }
    }

    /**
     * 获取当前用户信息
     */
    getCurrentUser() {
        const userStr = localStorage.getItem('current_user');
        return userStr ? JSON.parse(userStr) : null;
    }

    /**
     * 设置当前用户信息
     */
    setCurrentUser(user) {
        if (user) {
            localStorage.setItem('current_user', JSON.stringify(user));
        } else {
            localStorage.removeItem('current_user');
        }
    }

    /**
     * 检查是否已登录
     */
    isAuthenticated() {
        return !!this.token && !!this.getCurrentUser();
    }

    /**
     * 构建请求头
     */
    getHeaders(includeAuth = true) {
        const headers = {
            'Content-Type': 'application/json',
        };

        if (includeAuth && this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        return headers;
    }

    /**
     * 通用HTTP请求方法
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: this.getHeaders(options.includeAuth !== false),
            ...options,
        };

        try {
            console.log(`[API] ${config.method || 'GET'} ${url}`);
            const response = await fetch(url, config);
            
            // 如果是401错误，可能是令牌过期
            if (response.status === 401) {
                this.handleAuthError();
                throw new Error('认证失败，请重新登录');
            }

            // 如果响应不是JSON格式，直接返回文本
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return await response.text();
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            console.log(`[API] 响应成功:`, data);
            return data;
        } catch (error) {
            console.error(`[API] 请求失败:`, error);
            throw error;
        }
    }

    /**
     * 处理认证错误
     */
    handleAuthError() {
        this.setToken(null);
        this.setCurrentUser(null);
        // 如果不在登录页面，跳转到登录页面
        if (window.location.pathname !== '/pages/login.html') {
            window.location.href = '/login';
        }
    }

    /**
     * GET请求
     */
    async get(endpoint, params = {}) {
        const url = new URL(`${this.baseURL}${endpoint}`, window.location.origin);
        Object.keys(params).forEach(key => {
            if (params[key] !== undefined && params[key] !== null) {
                url.searchParams.append(key, params[key]);
            }
        });

        return await this.request(endpoint + '?' + url.searchParams.toString(), {
            method: 'GET',
        });
    }

    /**
     * POST请求
     */
    async post(endpoint, data = {}, options = {}) {
        return await this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
            ...options,
        });
    }

    /**
     * PUT请求
     */
    async put(endpoint, data = {}) {
        return await this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    /**
     * DELETE请求
     */
    async delete(endpoint) {
        return await this.request(endpoint, {
            method: 'DELETE',
        });
    }

    // ==================== 认证相关API ====================

    /**
     * 用户注册
     */
    async register(userData) {
        const response = await this.post('/auth/register', userData, { includeAuth: false });
        return response;
    }

    /**
     * 用户登录
     */
    async login(credentials) {
        const response = await this.post('/auth/login', credentials, { includeAuth: false });
        if (response.access_token) {
            this.setToken(response.access_token);
            this.setCurrentUser(response.user);
        }
        return response;
    }

    /**
     * 用户登出
     */
    async logout() {
        try {
            await this.post('/auth/logout');
        } finally {
            this.setToken(null);
            this.setCurrentUser(null);
        }
    }

    /**
     * 验证令牌
     */
    async verifyToken() {
        const response = await this.post('/auth/verify');
        return response;
    }

    /**
     * 获取当前用户（从服务器）
     */
    async getMe() {
        const response = await this.get('/auth/me');
        this.setCurrentUser(response);
        return response;
    }

    // ==================== 用户管理API ====================

    /**
     * 获取用户资料
     */
    async getUserProfile() {
        return await this.get('/user/profile');
    }

    /**
     * 更新用户资料
     */
    async updateUserProfile(profileData) {
        return await this.put('/user/profile', profileData);
    }

    /**
     * 修改密码
     */
    async changePassword(passwordData) {
        return await this.post('/user/change-password', passwordData);
    }

    /**
     * 获取用户活动记录
     */
    async getUserActivities(params = {}) {
        return await this.get('/user/activities', params);
    }

    /**
     * 获取用户统计信息
     */
    async getUserStats() {
        return await this.get('/user/stats');
    }

    /**
     * 获取用户登录历史记录
     */
    async getLoginHistory(params = {}) {
        return await this.get('/user/login-history', params);
    }

    /**
     * 删除用户账户
     */
    async deleteAccount() {
        return await this.delete('/user/account');
    }

    // ==================== API密钥管理API ====================

    /**
     * 获取API密钥列表
     */
    async getApiKeys() {
        return await this.get('/api-keys');
    }

    /**
     * 创建API密钥
     */
    async createApiKey(keyData) {
        return await this.post('/api-keys', keyData);
    }

    /**
     * 更新API密钥
     */
    async updateApiKey(keyId, keyData) {
        return await this.put(`/api-keys/${keyId}`, keyData);
    }

    /**
     * 删除API密钥
     */
    async deleteApiKey(keyId) {
        return await this.delete(`/api-keys/${keyId}`);
    }

    // ==================== 设备管理API ====================

    /**
     * 获取设备列表
     */
    async getDevices() {
        // 兼容后端返回两种结构：
        // 1) 直接返回设备数组
        // 2) 返回对象 { success, total, message, devices: [...] }
        const data = await this.get('/devices');
        if (Array.isArray(data)) {
            return data;
        }
        if (data && Array.isArray(data.devices)) {
            return data.devices;
        }
        return [];
    }

    // ===== 小米账户管理 =====
    
    /**
     * 获取小米账户列表
     */
    async getMiAccounts() {
        return await this.get('/mi-accounts');
    }

    /**
     * 创建小米账户（简化版本）
     */
    async createMiAccountSimplified(accountData) {
        return await this.post('/mi-accounts/simplified', accountData);
    }

    /**
     * 刷新指定小米账户的设备列表
     */
    async refreshAccountDevices(accountId) {
        return await this.post(`/mi-accounts/${accountId}/refresh-devices`);
    }



    /**
     * 刷新所有小米账户的设备列表
     */
    async refreshAllDevices() {
        return await this.post('/mi-accounts/refresh-all-devices');
    }

    /**
     * 创建小米账户（传统方式）
     */
    async createMiAccount(accountData) {
        return await this.post('/mi-accounts', accountData);
    }

    /**
     * 获取小米账户详情
     */
    async getMiAccountDetail(accountId) {
        return await this.get(`/mi-accounts/${accountId}`);
    }

    /**
     * 更新小米账户
     */
    async updateMiAccount(accountId, accountData) {
        return await this.put(`/mi-accounts/${accountId}`, accountData);
    }

    /**
     * 删除小米账户
     */
    async deleteMiAccount(accountId) {
        return await this.delete(`/mi-accounts/${accountId}`);
    }

    /**
     * 同步小米账户
     */
    async syncMiAccount(accountId) {
        return await this.post(`/mi-accounts/${accountId}/sync`);
    }

    /**
     * 获取小米账户统计信息
     */
    async getMiAccountStats() {
        return await this.get('/mi-accounts/stats/summary');
    }

    /**
     * 测试小米认证
     */
    async testMiAuthentication(authData) {
        return await this.post('/mi-accounts/test-auth', authData);
    }

    /**
     * 测试小米账户连接
     */
    async testMiAccountConnection(accountId) {
        return await this.post(`/mi-accounts/${accountId}/test-connection`);
    }

    /**
     * 更新小米账户状态
     */
    async updateMiAccountStatus(accountId, statusData) {
        return await this.put(`/mi-accounts/${accountId}`, statusData);
    }

    /**
     * 语音播放
     */
    async speak(speakData) {
        return await this.post('/speak', speakData);
    }

    /**
     * 获取播放任务状态
     */
    async getSpeakStatus(taskId) {
        return await this.get(`/speak/status/${taskId}`);
    }

    /**
     * 设置设备音量
     */
    async setVolume(volumeData) {
        const { device_id, volume } = volumeData;
        return await this.post(`/devices/${device_id}/volume?volume=${volume}`);
    }

    // ==================== 通知渠道管理API ====================

    /**
     * 获取通知渠道列表
     */
    async getChannels() {
        return await this.get('/channels');
    }

    /**
     * 创建通知渠道
     */
    async createChannel(channelData) {
        return await this.post('/channels', channelData);
    }

    /**
     * 更新通知渠道
     */
    async updateChannel(channelId, channelData) {
        return await this.put(`/channels/${channelId}`, channelData);
    }

    /**
     * 删除通知渠道
     */
    async deleteChannel(channelId) {
        return await this.delete(`/channels/${channelId}`);
    }

    /**
     * 测试通知渠道
     */
    async testChannel(channelId) {
        return await this.post(`/channels/${channelId}/test`);
    }

    /**
     * 统一推送消息
     */
    async sendNotification(notificationData) {
        return await this.post('/notify/send', notificationData);
    }

    // ==================== 系统API ====================

    /**
     * 健康检查
     */
    async healthCheck() {
        return await this.get('/health', {}, { includeAuth: false });
    }
}

/**
 * 通知系统
 */
class NotificationSystem {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // 创建通知容器
        this.container = document.createElement('div');
        this.container.className = 'notification-container';
        this.container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
        `;
        document.body.appendChild(this.container);
    }

    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.style.cssText = `
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 10px;
            padding: 16px;
            border-left: 4px solid;
            animation: slideIn 0.3s ease;
            cursor: pointer;
        `;

        // 设置不同类型的颜色
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        notification.style.borderLeftColor = colors[type] || colors.info;

        // 添加图标和消息
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };

        notification.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 8px;">
                <span style="font-size: 18px;">${icons[type] || icons.info}</span>
                <div style="flex: 1;">
                    <div style="color: #1f2937; font-weight: 500; margin-bottom: 4px;">
                        ${type.charAt(0).toUpperCase() + type.slice(1)}
                    </div>
                    <div style="color: #6b7280; font-size: 14px;">${message}</div>
                </div>
                <button style="background: none; border: none; font-size: 18px; color: #9ca3af; cursor: pointer; padding: 0; margin-left: 8px;">×</button>
            </div>
        `;

        // 添加样式
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes slideOut {
                from {
                    transform: translateX(0);
                    opacity: 1;
                }
                to {
                    transform: translateX(100%);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);

        // 点击关闭
        const closeBtn = notification.querySelector('button');
        closeBtn.addEventListener('click', () => this.remove(notification));
        notification.addEventListener('click', () => this.remove(notification));

        // 添加到容器
        this.container.appendChild(notification);

        // 自动移除
        if (duration > 0) {
            setTimeout(() => this.remove(notification), duration);
        }

        return notification;
    }

    remove(notification) {
        if (notification && notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }

    success(message, duration) {
        return this.show(message, 'success', duration);
    }

    error(message, duration) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration) {
        return this.show(message, 'info', duration);
    }
}

/**
 * 加载状态管理
 */
class LoadingManager {
    constructor() {
        this.overlay = null;
        this.init();
    }

    init() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'loading-overlay';
        this.overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9998;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        `;

        this.overlay.innerHTML = `
            <div style="background: white; border-radius: 8px; padding: 24px; display: flex; flex-direction: column; align-items: center; gap: 16px;">
                <div class="loading" style="width: 32px; height: 32px; border: 3px solid #e5e7eb; border-top-color: #4f46e5; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <div style="color: #6b7280; font-size: 14px;">加载中...</div>
            </div>
        `;

        document.body.appendChild(this.overlay);
    }

    show() {
        this.overlay.style.opacity = '1';
        this.overlay.style.visibility = 'visible';
    }

    hide() {
        this.overlay.style.opacity = '0';
        this.overlay.style.visibility = 'hidden';
    }
}

// 全局实例
window.apiClient = new ApiClient();
window.notifications = new NotificationSystem();
window.loadingManager = new LoadingManager();

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ApiClient, NotificationSystem, LoadingManager };
}
