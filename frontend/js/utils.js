/**
 * 爱通知小爱音箱消息推送统一API平台 - 工具函数
 */

/**
 * 格式化日期时间
 */
function formatDateTime(dateString, options = {}) {
    if (!dateString) return '-';
    
    const date = new Date(dateString);
    const defaultOptions = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    };
    
    return date.toLocaleString('zh-CN', { ...defaultOptions, ...options });
}

/**
 * 格式化相对时间
 */
function formatRelativeTime(dateString) {
    if (!dateString) return '-';
    
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    
    return formatDateTime(dateString, { month: 'short', day: 'numeric' });
}

/**
 * 复制文本到剪贴板
 */
async function copyToClipboard(text) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            // 降级方案
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            document.execCommand('copy');
            textArea.remove();
        }
        window.notifications.success('已复制到剪贴板');
        return true;
    } catch (error) {
        console.error('复制失败:', error);
        window.notifications.error('复制失败');
        return false;
    }
}

/**
 * 防抖函数
 */
function debounce(func, wait, immediate = false) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

/**
 * 节流函数
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 生成随机ID
 */
function generateId(length = 8) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

/**
 * 验证邮箱格式
 */
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * 验证密码强度
 */
function validatePassword(password) {
    const minLength = 8;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumbers = /\d/.test(password);
    const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>]/.test(password);
    
    const score = [
        password.length >= minLength,
        hasUpperCase,
        hasLowerCase,
        hasNumbers,
        hasSpecialChar
    ].filter(Boolean).length;
    
    let strength = 'weak';
    if (score >= 4) strength = 'strong';
    else if (score >= 3) strength = 'medium';
    
    return {
        valid: score >= 3,
        strength,
        score,
        requirements: {
            minLength: password.length >= minLength,
            hasUpperCase,
            hasLowerCase,
            hasNumbers,
            hasSpecialChar
        }
    };
}

/**
 * 文件大小格式化
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 数字格式化
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

/**
 * 获取状态徽章HTML
 */
function getStatusBadge(status, text) {
    const badgeClasses = {
        active: 'badge-success',
        inactive: 'badge-gray',
        expired: 'badge-danger',
        pending: 'badge-warning',
        success: 'badge-success',
        error: 'badge-danger',
        warning: 'badge-warning',
        info: 'badge-primary'
    };
    
    const className = badgeClasses[status] || 'badge-gray';
    return `<span class="badge ${className}">${text || status}</span>`;
}

/**
 * 权限配置转换为可读文本
 */
function formatPermissions(permissions) {
    const permissionNames = {
        speak: '语音播放',
        get_devices: '获取设备',
        manage_devices: '管理设备',
        stop_speak: '停止播放',
        set_volume: '设置音量',
        get_status: '获取状态'
    };
    
    const enabled = Object.entries(permissions)
        .filter(([key, value]) => value)
        .map(([key]) => permissionNames[key] || key);
    
    return enabled.length > 0 ? enabled.join(', ') : '无权限';
}

/**
 * 表单验证
 */
class FormValidator {
    constructor(form) {
        this.form = form;
        this.rules = {};
        this.errors = {};
    }
    
    /**
     * 添加验证规则
     */
    addRule(fieldName, rule) {
        if (!this.rules[fieldName]) {
            this.rules[fieldName] = [];
        }
        this.rules[fieldName].push(rule);
        return this;
    }
    
    /**
     * 验证表单
     */
    validate() {
        this.errors = {};
        const formData = new FormData(this.form);
        
        for (const [fieldName, rules] of Object.entries(this.rules)) {
            const value = formData.get(fieldName) || '';
            
            for (const rule of rules) {
                const result = rule.validator(value, formData);
                if (result !== true) {
                    if (!this.errors[fieldName]) {
                        this.errors[fieldName] = [];
                    }
                    this.errors[fieldName].push(result);
                    break; // 只显示第一个错误
                }
            }
        }
        
        this.displayErrors();
        return Object.keys(this.errors).length === 0;
    }
    
    /**
     * 显示错误信息
     */
    displayErrors() {
        // 清除现有错误
        this.form.querySelectorAll('.form-error').forEach(el => el.remove());
        this.form.querySelectorAll('.error').forEach(el => el.classList.remove('error'));
        
        // 显示新错误
        for (const [fieldName, errors] of Object.entries(this.errors)) {
            const field = this.form.querySelector(`[name="${fieldName}"]`);
            if (field) {
                field.classList.add('error');
                
                const errorDiv = document.createElement('div');
                errorDiv.className = 'form-error';
                errorDiv.textContent = errors[0];
                field.parentNode.appendChild(errorDiv);
            }
        }
    }
    
    /**
     * 获取表单数据
     */
    getData() {
        const formData = new FormData(this.form);
        const data = {};
        for (const [key, value] of formData.entries()) {
            data[key] = value;
        }
        return data;
    }
}

/**
 * 常用验证规则
 */
const ValidationRules = {
    required: (message = '此字段为必填项') => ({
        validator: (value) => value.trim() !== '' || message
    }),
    
    email: (message = '请输入有效的邮箱地址') => ({
        validator: (value) => !value || validateEmail(value) || message
    }),
    
    minLength: (length, message) => ({
        validator: (value) => value.length >= length || message || `最少需要${length}个字符`
    }),
    
    maxLength: (length, message) => ({
        validator: (value) => value.length <= length || message || `最多允许${length}个字符`
    }),
    
    password: (message = '密码至少8位，包含大小写字母和数字') => ({
        validator: (value) => {
            const result = validatePassword(value);
            return result.valid || message;
        }
    }),
    
    confirmPassword: (passwordField, message = '两次输入的密码不一致') => ({
        validator: (value, formData) => {
            const password = formData.get(passwordField);
            return value === password || message;
        }
    }),
    
    pattern: (regex, message) => ({
        validator: (value) => !value || regex.test(value) || message
    })
};

/**
 * 模态框管理器
 */
class ModalManager {
    constructor() {
        this.modals = new Map();
    }
    
    /**
     * 创建模态框
     */
    create(id, title, content, options = {}) {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.id = id;
        
        modal.innerHTML = `
            <div class="modal">
                <div class="modal-header">
                    <h3 class="modal-title">${title}</h3>
                </div>
                <div class="modal-body">
                    ${content}
                </div>
                ${options.showFooter !== false ? `
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-dismiss="modal">取消</button>
                    ${options.confirmText ? `<button type="button" class="btn btn-primary" data-confirm="modal">${options.confirmText}</button>` : ''}
                </div>
                ` : ''}
            </div>
        `;
        
        document.body.appendChild(modal);
        this.modals.set(id, modal);
        
        // 绑定事件
        modal.addEventListener('click', (e) => {
            if (e.target === modal || e.target.getAttribute('data-dismiss') === 'modal') {
                this.close(id);
            }
        });
        
        if (options.onConfirm) {
            const confirmBtn = modal.querySelector('[data-confirm="modal"]');
            if (confirmBtn) {
                confirmBtn.addEventListener('click', () => {
                    options.onConfirm();
                    if (options.autoClose !== false) {
                        this.close(id);
                    }
                });
            }
        }
        
        return modal;
    }
    
    /**
     * 显示模态框
     */
    show(id) {
        const modal = this.modals.get(id);
        if (modal) {
            modal.classList.add('active');
        }
    }
    
    /**
     * 关闭模态框
     */
    close(id) {
        const modal = this.modals.get(id);
        if (modal) {
            modal.classList.remove('active');
        }
    }
    
    /**
     * 移除模态框
     */
    remove(id) {
        const modal = this.modals.get(id);
        if (modal) {
            modal.remove();
            this.modals.delete(id);
        }
    }
    
    /**
     * 确认对话框
     */
    confirm(title, message, onConfirm) {
        const id = 'confirm-modal-' + generateId();
        this.create(id, title, `<p>${message}</p>`, {
            confirmText: '确认',
            onConfirm: onConfirm
        });
        this.show(id);
        
        // 自动清理
        setTimeout(() => this.remove(id), 30000);
    }
    
    /**
     * 提示对话框
     */
    alert(title, message) {
        const id = 'alert-modal-' + generateId();
        this.create(id, title, `<p>${message}</p>`, {
            showFooter: false
        });
        this.show(id);
        
        // 点击任意地方关闭
        setTimeout(() => {
            const modal = this.modals.get(id);
            if (modal) {
                modal.addEventListener('click', () => this.close(id));
                setTimeout(() => this.remove(id), 10000);
            }
        }, 100);
    }
}

// 全局实例
window.modalManager = new ModalManager();

// 工具函数绑定到全局
window.utils = {
    formatDateTime,
    formatRelativeTime,
    copyToClipboard,
    debounce,
    throttle,
    generateId,
    validateEmail,
    validatePassword,
    formatFileSize,
    formatNumber,
    getStatusBadge,
    formatPermissions,
    FormValidator,
    ValidationRules,
    ModalManager
};
