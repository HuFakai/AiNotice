/**
 * API统计分析页面JavaScript
 * 处理数据获取、图表渲染和用户交互
 */

// 全局变量
let currentChart = null;
let currentPeriod = '24h';
let currentDevice = '';
let currentApiKeyName = '';
let currentSpeakText = '';
let currentPage = 1;
const pageSize = 20;
let refreshInterval = null;

// API基础URL（同源相对路径，由 FastAPI 静态托管，避免硬编码端口）
const API_BASE_URL = '/api/v1';

/**
 * 检查用户登录状态
 */
function isLoggedIn() {
    return window.apiClient && window.apiClient.isAuthenticated();
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializePage();
});

/**
 * 初始化页面
 */
function initializePage() {
    // 检查用户登录状态
    if (!isLoggedIn()) {
        // 重定向到登录页面，并携带当前页面作为返回地址
        const currentPage = encodeURIComponent(window.location.pathname);
        window.location.href = `/pages/login.html?redirect=${currentPage}`;
        return;
    }

    // 加载用户信息
    loadUserInfo();
    
    // 绑定事件监听器
    bindEventListeners();
    
    // 加载初始数据
    loadInitialData();
    
    // 设置自动刷新
    startAutoRefresh();
}

/**
 * 绑定事件监听器
 */
function bindEventListeners() {
    // 添加延迟确保DOM完全加载
    setTimeout(() => {
        // 时间范围选择
        const periodSelect = document.getElementById('periodSelect');
        if (periodSelect) {
            periodSelect.addEventListener('change', function() {
                const period = this.value;
                currentPeriod = period;
                
                const customDateRange = document.getElementById('customDateRange');
                if (customDateRange) {
                    if (period === 'custom') {
                        customDateRange.style.display = 'flex';
                    } else {
                        customDateRange.style.display = 'none';
                        refreshData();
                    }
                }
            });
        } else {
            console.warn('periodSelect element not found');
        }
        
        // 自定义日期范围
        const startDate = document.getElementById('startDate');
        if (startDate) {
            startDate.addEventListener('change', refreshData);
        } else {
            console.warn('startDate element not found');
        }
        
        const endDate = document.getElementById('endDate');
        if (endDate) {
            endDate.addEventListener('change', refreshData);
        } else {
            console.warn('endDate element not found');
        }
        
        // 设备筛选
        const deviceFilter = document.getElementById('deviceFilter');
        if (deviceFilter) {
            deviceFilter.addEventListener('change', function() {
                currentDevice = this.value;
                refreshData();
            });
        } else {
            console.warn('deviceFilter element not found');
        }
        
        // API密钥名称筛选（下拉选择器）
        const apiKeyNameFilter = document.getElementById('apiKeyNameFilter');
        if (apiKeyNameFilter) {
            apiKeyNameFilter.addEventListener('change', function() {
                currentApiKeyName = this.value;
                refreshData();
            });
        } else {
            console.warn('apiKeyNameFilter element not found');
        }
        
        // 播报内容筛选（保持输入框，但移除自动搜索）
        const speakTextFilter = document.getElementById('speakTextFilter');
        if (speakTextFilter) {
            // 支持回车键搜索
            speakTextFilter.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });
        } else {
            console.warn('speakTextFilter element not found');
        }
    }, 100); // 100ms延迟
}

/**
 * 加载用户信息
 */
async function loadUserInfo() {
    try {
        const user = await window.apiClient.getMe();
        const userDisplayName = document.getElementById('userDisplayName');
        if (userDisplayName) {
            userDisplayName.textContent = user.display_name || user.username || '用户';
        }
    } catch (error) {
        console.error('加载用户信息失败:', error);
    }
}

/**
 * 加载初始数据
 */
async function loadInitialData() {
    try {
        console.log('开始加载初始数据...');
        // 并行加载所有数据
        const results = await Promise.allSettled([
            loadOverviewStats(),
            loadTrendChart(),
            loadCallLogs(),
            loadDevicesData(),
            loadDeviceOptions(),
            loadApiKeyOptions()
        ]);
        
        // 检查每个结果
        results.forEach((result, index) => {
            const functionNames = ['loadOverviewStats', 'loadTrendChart', 'loadCallLogs', 'loadDevicesData', 'loadDeviceOptions', 'loadApiKeyOptions'];
            if (result.status === 'rejected') {
                console.error(`${functionNames[index]} 失败:`, result.reason);
            } else {
                console.log(`${functionNames[index]} 成功`);
            }
        });
    } catch (error) {
        console.error('加载初始数据失败:', error);
        showError('加载数据失败，请刷新页面重试');
    }
}

/**
 * 加载统计概览
 */
async function loadOverviewStats() {
    try {
        const params = buildQueryParams();
        const queryObj = Object.fromEntries(params);
        const data = await window.apiClient.get('/analytics/speak/analytics', queryObj);
        updateOverviewStats(data.data.overview);
    } catch (error) {
        console.error('加载speak统计概览失败:', error);
        showError('加载speak统计概览失败');
    }
}

/**
 * 更新统计概览显示
 */
function updateOverviewStats(stats) {
    const totalCallsEl = document.getElementById('totalCalls');
    const successRateEl = document.getElementById('successRate');
    const avgResponseTimeEl = document.getElementById('avgResponseTime');
    const errorCountEl = document.getElementById('errorCount');
    
    if (totalCallsEl) totalCallsEl.textContent = formatNumber(stats.total_calls || 0);
    if (successRateEl) successRateEl.textContent = `${stats.success_rate || 0}%`;
    if (avgResponseTimeEl) avgResponseTimeEl.textContent = `${stats.avg_response_time_ms || 0}ms`;
    if (errorCountEl) errorCountEl.textContent = formatNumber(stats.failed_calls || 0);
    
    // 添加设备数量显示（如果有的话）
    if (stats.unique_devices !== undefined) {
        // 可以在页面上添加一个显示唯一设备数的元素
        console.log(`唯一设备数: ${stats.unique_devices}`);
    }
    
    // 计算错误次数
    const errorCount = stats.total_calls - (stats.total_calls * stats.success_rate / 100);
    if (errorCountEl) errorCountEl.textContent = formatNumber(Math.round(errorCount));
    
    // 这里可以添加变化趋势的计算和显示
    // 暂时隐藏变化指示器
    document.querySelectorAll('.stat-change').forEach(el => el.style.display = 'none');
}

/**
 * 加载趋势图表
 */
async function loadTrendChart() {
    try {
        const params = buildQueryParams();
        const queryObj = Object.fromEntries(params);
        const data = await window.apiClient.get('/analytics/speak/analytics', queryObj);
        renderTrendChart(data.data.time_series);
    } catch (error) {
        console.error('加载speak趋势图表失败:', error);
        showError('加载speak趋势图表失败');
    }
}

/**
 * 渲染趋势图表
 */
function renderTrendChart(timeSeriesData) {
    const chartElement = document.getElementById('trendChart');
    if (!chartElement) {
        console.warn('Trend chart element not found');
        return;
    }
    const ctx = chartElement.getContext('2d');
    
    // 销毁现有图表
    if (currentChart) {
        currentChart.destroy();
    }
    
    // 准备数据 - 根据时间范围优化标签格式
    const labels = timeSeriesData.map(item => {
        const date = new Date(item.timestamp);
        
        // 根据时间范围选择合适的显示格式
        if (currentPeriod === '24h') {
            // 24小时内显示月-日 小时:分钟
            return date.toLocaleString('zh-CN', { 
                month: 'short',
                day: 'numeric',
                hour: '2-digit', 
                minute: '2-digit'
            });
        } else if (currentPeriod === '7d') {
            // 7天内显示月-日
            return date.toLocaleDateString('zh-CN', { 
                month: 'short', 
                day: 'numeric'
            });
        } else if (currentPeriod === '30d' || currentPeriod === '90d') {
            // 30天或90天显示月-日
            return date.toLocaleDateString('zh-CN', { 
                month: 'short', 
                day: 'numeric'
            });
        } else {
            // 自定义范围，根据数据点数量决定格式
            const dataPointCount = timeSeriesData.length;
            if (dataPointCount <= 24) {
                // 数据点少，显示详细时间
                return date.toLocaleString('zh-CN', { 
                    month: 'short', 
                    day: 'numeric',
                    hour: '2-digit'
                });
            } else {
                // 数据点多，只显示日期
                return date.toLocaleDateString('zh-CN', { 
                    month: 'short', 
                    day: 'numeric'
                });
            }
        }
    });
    
    const callsData = timeSeriesData.map(item => item.calls);
    const successData = timeSeriesData.map(item => item.success_calls);
    const errorData = timeSeriesData.map(item => item.error_calls);
    
    // 创建图表
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '总调用量',
                data: callsData,
                borderColor: '#4f46e5',
                backgroundColor: 'rgba(79, 70, 229, 0.1)',
                tension: 0.4,
                fill: true
            }, {
                label: '成功调用',
                data: successData,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.4
            }, {
                label: '错误调用',
                data: errorData,
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: '时间'
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: '调用次数'
                    },
                    beginAtZero: true
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

/**
 * 加载设备统计数据
 */
async function loadDevicesData() {
    const loading = document.getElementById('devicesLoading');
    const content = document.getElementById('devicesContent');
    
    if (!loading || !content) {
        console.warn('Devices elements not found:', { loading: !!loading, content: !!content });
        return;
    }
    
    loading.style.display = 'flex';
    content.style.display = 'none';
    
    try {
        const params = buildQueryParams();
        const queryObj = Object.fromEntries(params);
        const data = await window.apiClient.get('/analytics/speak/devices', queryObj);
        renderDevicesTable(data.data.devices);
        loading.style.display = 'none';
        content.style.display = 'block';
    } catch (error) {
        console.error('加载设备统计数据失败:', error);
        if (loading) {
            loading.innerHTML = '<span style="color: var(--error-color);">加载失败</span>';
        }
    }
}

/**
 * 渲染设备统计表格
 */
function renderDevicesTable(devices) {
    const tbody = document.getElementById('devicesTableBody');
    tbody.innerHTML = '';
    
    devices.forEach(device => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${device.device_name || '-'}</td>
            <td><code>${device.device_id}</code></td>
            <td>${formatNumber(device.total_calls)}</td>
            <td>${formatNumber(device.success_count || 0)}</td>
            <td>
                <span class="status-badge ${device.success_rate >= 95 ? 'success' : device.success_rate >= 90 ? 'warning' : 'error'}">
                    ${device.success_rate}%
                </span>
            </td>
            <td>${device.avg_response_time}ms</td>
            <td>${formatDateTime(device.last_call_time)}</td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * 加载speak调用记录
 */
async function loadCallLogs(page = 1) {
    const loading = document.getElementById('logsLoading');
    const content = document.getElementById('logsContent');
    
    if (!loading || !content) {
        console.warn('Call logs elements not found:', { loading: !!loading, content: !!content });
        return;
    }
    
    if (page === 1) {
        loading.style.display = 'flex';
        content.style.display = 'none';
    }
    
    try {
        const params = buildQueryParams();
        params.append('page', page);
        params.append('limit', pageSize);
        
        const queryObj = Object.fromEntries(params);
        const data = await window.apiClient.get('/analytics/speak/call-logs', queryObj);
        renderCallLogsTable(data.data);
        renderPagination(data.pagination, 'logs');
        
        if (page === 1) {
            loading.style.display = 'none';
            content.style.display = 'block';
        }
    } catch (error) {
        console.error('加载speak调用记录失败:', error);
        if (page === 1 && loading) {
            loading.innerHTML = '<span style="color: var(--error-color);">加载失败</span>';
        }
    }
}

/**
 * 渲染调用记录表格
 */
function renderCallLogsTable(logs) {
    const tbody = document.getElementById('logsTableBody');
    
    if (!tbody) {
        console.warn('Logs table body element not found');
        return;
    }
    
    tbody.innerHTML = '';
    
    logs.forEach(log => {
        const row = document.createElement('tr');
        const statusClass = log.status_code >= 200 && log.status_code < 300 ? 'success' : 
                           log.status_code >= 400 && log.status_code < 500 ? 'warning' : 'error';
        
        row.innerHTML = `
            <td>${formatDateTime(log.created_at)}</td>
            <td>${log.device_name || '-'}</td>
            <td><code>${log.device_id || '-'}</code></td>
            <td>${log.api_key_name || '-'}</td>
            <td class="speak-text">${log.speak_text || '-'}</td>
            <td><span class="status-badge ${statusClass}">${log.status_code}</span></td>
            <td>${log.request_ip || '-'}</td>
        `;
        tbody.appendChild(row);
    });
}

/**
 * 加载设备选项
 */
async function loadDeviceOptions() {
    try {
        const params = buildQueryParams();
        const queryObj = Object.fromEntries(params);
        const data = await window.apiClient.get('/analytics/speak/devices', queryObj);
        const select = document.getElementById('deviceFilter');
        
        if (!select) {
            console.warn('Device filter select element not found');
            return;
        }
        
        // 清空现有选项（保留"全部设备"）
        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }
        
        // 添加设备选项
        data.data.devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.device_id;
            option.textContent = device.device_name || device.device_id;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('加载设备选项失败:', error);
    }
}

/**
 * 加载API密钥选项
 */
async function loadApiKeyOptions() {
    try {
        console.log('开始加载API密钥选项...');
        const data = await window.apiClient.get('/api-keys');
        console.log('API密钥数据:', data);
        const select = document.getElementById('apiKeyNameFilter');
        
        if (!select) {
            console.warn('API key filter select element not found');
            return;
        }
        
        // 清空现有选项（保留"全部密钥"）
        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }
        
        // 检查数据结构
        const apiKeys = data.data || data.api_keys || data;
        console.log('处理的API密钥数组:', apiKeys);
        
        if (Array.isArray(apiKeys)) {
            // 添加API密钥选项
            apiKeys.forEach(apiKey => {
                const option = document.createElement('option');
                option.value = apiKey.name || apiKey.key_name;
                option.textContent = apiKey.name || apiKey.key_name;
                select.appendChild(option);
            });
            console.log(`成功加载${apiKeys.length}个API密钥选项`);
        } else {
            console.warn('API密钥数据不是数组格式:', apiKeys);
        }
    } catch (error) {
        console.error('加载API密钥选项失败:', error);
    }
}

/**
 * 执行搜索
 */
function performSearch() {
    const speakTextFilter = document.getElementById('speakTextFilter');
    if (speakTextFilter) {
        currentSpeakText = speakTextFilter.value.trim();
        refreshData();
    }
}

// 将performSearch函数添加到全局作用域
window.performSearch = performSearch;

/**
 * 构建查询参数
 */
function buildQueryParams() {
    const params = new URLSearchParams();
    
    if (currentPeriod === 'custom') {
        const startDateEl = document.getElementById('startDate');
        const endDateEl = document.getElementById('endDate');
        const startDate = startDateEl ? startDateEl.value : '';
        const endDate = endDateEl ? endDateEl.value : '';
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
    } else {
        params.append('period', currentPeriod);
    }
    
    if (currentDevice) {
        params.append('device_id', currentDevice);
    }
    
    if (currentApiKeyName) {
        params.append('api_key_name', currentApiKeyName);
    }
    
    if (currentSpeakText) {
        params.append('speak_text', currentSpeakText);
    }
    
    return params;
}

/**
 * 渲染分页控件
 */
function renderPagination(pagination, type) {
    const info = document.getElementById(`${type}Info`);
    const controls = document.getElementById(`${type}Controls`);
    
    if (!info || !controls) {
        console.warn('Pagination elements not found:', { info: !!info, controls: !!controls });
        return;
    }
    
    // 更新信息
    const start = (pagination.page - 1) * pagination.limit + 1;
    const end = Math.min(pagination.page * pagination.limit, pagination.total);
    info.textContent = `显示 ${start}-${end} 条，共 ${pagination.total} 条记录`;
    
    // 更新控件
    controls.innerHTML = '';
    
    // 上一页按钮
    if (pagination.has_prev) {
        const prevBtn = document.createElement('button');
        prevBtn.className = 'btn btn-secondary';
        prevBtn.textContent = '上一页';
        prevBtn.onclick = () => {
            if (type === 'logs') {
                loadCallLogs(pagination.page - 1);
            }
        };
        controls.appendChild(prevBtn);
    }
    
    // 页码显示
    const pageInfo = document.createElement('span');
    pageInfo.textContent = `第 ${pagination.page} 页，共 ${pagination.pages} 页`;
    pageInfo.style.margin = '0 1rem';
    pageInfo.style.fontSize = '0.875rem';
    pageInfo.style.color = 'var(--text-secondary)';
    controls.appendChild(pageInfo);
    
    // 下一页按钮
    if (pagination.has_next) {
        const nextBtn = document.createElement('button');
        nextBtn.className = 'btn btn-secondary';
        nextBtn.textContent = '下一页';
        nextBtn.onclick = () => {
            if (type === 'logs') {
                loadCallLogs(pagination.page + 1);
            }
        };
        controls.appendChild(nextBtn);
    }
}

/**
 * 切换图表类型
 */
function switchChart(type) {
    // 更新标签页状态
    document.querySelectorAll('.chart-container .tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
}

/**
 * 切换详细分析标签页
 */
function switchTab(tabName) {
    // 更新标签页状态
    document.querySelectorAll('.chart-container:last-child .tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // 隐藏所有内容
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // 显示选中的内容
    const targetTab = document.getElementById(`${tabName}Tab`);
    if (targetTab) {
        targetTab.classList.add('active');
    }
    
    // 根据需要加载数据
    switch (tabName) {
        case 'devices':
            loadDevicesData();
            break;
        case 'logs':
            loadCallLogs();
            break;
    }
}

/**
 * 刷新数据
 */
function refreshData() {
    loadOverviewStats();
    loadTrendChart();
    loadCallLogs();
    loadDevicesData();
}



/**
 * 开始自动刷新
 */
function startAutoRefresh() {
    // 每30秒刷新一次统计概览
    refreshInterval = setInterval(() => {
        loadOverviewStats();
    }, 30000);
}

/**
 * 停止自动刷新
 */
function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

/**
 * 显示错误信息
 */
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    
    if (!errorDiv) {
        console.warn('Error message element not found');
        console.error('Error:', message);
        return;
    }
    
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    // 3秒后自动隐藏
    setTimeout(() => {
        if (errorDiv) {
            errorDiv.style.display = 'none';
        }
    }, 3000);
}

/**
 * 格式化数字
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

/**
 * 格式化字节数
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 格式化日期时间
 */
function formatDateTime(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * 格式化日期
 */
function formatDate(date, format = 'yyyy-MM-dd') {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    
    switch(format) {
        case 'yyyy-MM-dd':
            return `${year}-${month}-${day}`;
        case 'MM-dd':
            return `${month}-${day}`;
        case 'yyyy-MM-dd HH:mm':
            return `${year}-${month}-${day} ${hours}:${minutes}`;
        default:
            return d.toISOString().split('T')[0];
    }
}

// 页面卸载时清理
/**
 * 用户登出
 */
function logout() {
    // 清除本地存储的认证信息
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    // 停止自动刷新
    stopAutoRefresh();
    
    // 重定向到登录页面
    window.location.href = '/login';
}

window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
    if (currentChart) {
        currentChart.destroy();
    }
});