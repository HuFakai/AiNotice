/**
 * 通知渠道管理页面逻辑控制
 */

// 通道类型元数据
const CHANNEL_METADATA = {
    email: { name: "SMTP 邮箱", icon: "fa-envelope", class: "email", desc: "通过电子邮件 SMTP 服务发送报警与通知。" },
    dingtalk: { name: "钉钉机器人", icon: "fa-comment-dots", class: "dingtalk", desc: "发送群组消息到钉钉自定义群机器人。" },
    feishu: { name: "飞书机器人", icon: "fa-dove", class: "feishu", desc: "发送群组卡片消息到飞书群机器人。" },
    wechat: { name: "企微机器人", icon: "fa-building", class: "wechat", desc: "发送Markdown/文本通知到企业微信群机器人。" },
    webhook: { name: "通用 Webhook", icon: "fa-anchor", class: "webhook", desc: "当触发通知时，向指定的 HTTP 地址发送 POST/GET 回调。" },
    speak: { name: "小爱音箱", icon: "fa-volume-high", class: "speak", desc: "控制您绑定的小爱音箱直接进行语音播报文字。" }
};

let allChannels = [];

// 页面加载完成后自动获取数据
document.addEventListener("DOMContentLoaded", () => {
    loadChannels();
});

/**
 * 获取用户的通知通道列表并渲染
 */
async function loadChannels() {
    const listContainer = document.getElementById("channelsList");
    try {
        window.loadingManager.show();
        allChannels = await window.apiClient.getChannels();
        renderChannels();
    } catch (err) {
        console.error("加载通道失败:", err);
        window.notifications.error("加载通知渠道失败: " + err.message);
        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon"><i class="fas fa-triangle-exclamation"></i></div>
                <p>加载通知渠道失败了</p>
                <button class="btn btn-primary mt-md" onclick="loadChannels()">重试</button>
            </div>
        `;
    } finally {
        window.loadingManager.hide();
    }
}

/**
 * 渲染通道卡片
 */
function renderChannels() {
    const listContainer = document.getElementById("channelsList");
    
    if (!allChannels || allChannels.length === 0) {
        listContainer.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-state-icon"><i class="fas fa-bullhorn"></i></div>
                <h3>暂无通知渠道</h3>
                <p>添加通知渠道，即可在 API 触发时轻松分发告警、日常通知或智能播报</p>
                <button class="btn btn-primary mt-md" onclick="openCreateModal()">创建第一个通知渠道</button>
            </div>
        `;
        return;
    }

    listContainer.innerHTML = allChannels.map(channel => {
        const meta = CHANNEL_METADATA[channel.channel_type] || { name: "未知类型", icon: "fa-circle-question", class: "webhook", desc: "" };
        const statusText = channel.is_active ? "已启用" : "已禁用";
        const statusClass = channel.is_active ? "badge-success" : "badge-gray";
        
        // 解析关键配置以显示在卡片上
        let configPreview = "";
        const cfg = channel.config || {};
        if (channel.channel_type === "email") {
            configPreview = `服务器: <code>${cfg.smtp_host || '-'}</code><br>发件人: ${cfg.smtp_user || '-'}`;
        } else if (channel.channel_type === "speak") {
            configPreview = `设备ID: <code>${cfg.device_id ? cfg.device_id.substring(0, 15) + '...' : '默认'}</code><br>默认音量: ${cfg.volume || '未指定'}`;
        } else {
            const url = cfg.webhook_url || cfg.url || "";
            configPreview = `链接: <code>${url ? url.substring(0, 32) + '...' : '-'}</code>`;
        }

        return `
            <div class="channel-card">
                <div>
                    <div class="channel-card-header">
                        <div class="channel-icon ${meta.class}">
                            <i class="fas ${meta.icon}"></i>
                        </div>
                        <div class="channel-info">
                            <h4 class="channel-name">${utils.escapeHtml(channel.name)}</h4>
                            <span class="channel-type-badge">${meta.name}</span>
                            <span class="badge ${statusClass}" style="margin-left: 6px;">${statusText}</span>
                        </div>
                    </div>
                    <div class="channel-details">
                        <p style="margin-bottom: 8px; font-size: 0.78rem; opacity: 0.85;">${meta.desc}</p>
                        <div style="background: var(--surface-hover); padding: 8px 12px; border-radius: var(--radius-sm); font-family: inherit;">
                            ${configPreview}
                        </div>
                    </div>
                </div>
                
                <div class="channel-card-actions">
                    <button class="btn btn-sm btn-outline" onclick="testChannel(${channel.id})" title="测试通道发送">
                        <i class="fas fa-paper-plane"></i> 测试
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="openEditModal(${channel.id})">
                        <i class="fas fa-pen"></i> 编辑
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteChannel(${channel.id}, '${utils.escapeHtml(channel.name)}')">
                        <i class="fas fa-trash"></i> 删除
                    </button>
                </div>
            </div>
        `;
    }).join("");
}

/**
 * 新增渠道，打开弹框
 */
function openCreateModal() {
    document.getElementById("modalTitle").textContent = "新增通知渠道";
    document.getElementById("channelForm").reset();
    document.getElementById("channelId").value = "";
    document.getElementById("channelType").disabled = false;
    toggleConfigFields();
    document.getElementById("channelModal").classList.add("active");
}

/**
 * 根据选择的通知渠道展示不同表单内容
 */
function toggleConfigFields() {
    const type = document.getElementById("channelType").value;
    
    // 隐藏所有配置块
    document.querySelectorAll(".config-field-group").forEach(el => {
        el.classList.remove("active");
    });

    // 激活选中的配置块
    if (type) {
        const configBlock = document.getElementById(`config_${type}`);
        if (configBlock) {
            configBlock.classList.add("active");
        }
    }
}

/**
 * 关闭模态框
 */
function closeModal(id) {
    document.getElementById(id).classList.remove("active");
}

/**
 * 打开编辑弹窗并数据回填
 */
async function openEditModal(channelId) {
    try {
        window.loadingManager.show();
        // 获取渠道详情
        const channel = await window.apiClient.request(`/channels/${channelId}`, { method: "GET" });
        
        document.getElementById("modalTitle").textContent = "编辑通知渠道";
        document.getElementById("channelId").value = channel.id;
        document.getElementById("channelName").value = channel.name;
        document.getElementById("channelType").value = channel.channel_type;
        document.getElementById("channelType").disabled = true; // 编辑时不允许修改类型
        document.getElementById("channelActive").checked = channel.is_active;

        toggleConfigFields();

        // 填充通道具体配置
        const cfg = channel.config || {};
        if (channel.channel_type === "email") {
            document.getElementById("email_smtp_host").value = cfg.smtp_host || "";
            document.getElementById("email_smtp_port").value = cfg.smtp_port || "";
            document.getElementById("email_smtp_user").value = cfg.smtp_user || "";
            document.getElementById("email_smtp_password").value = ""; // 密码不回填，修改时若为空则后端保留原密码
            document.getElementById("email_from_address").value = cfg.from_address || "";
            document.getElementById("email_to_addresses").value = cfg.to_addresses || "";
        } else if (channel.channel_type === "dingtalk") {
            document.getElementById("dingtalk_webhook_url").value = cfg.webhook_url || "";
            document.getElementById("dingtalk_secret").value = cfg.secret || "";
            document.getElementById("dingtalk_msg_type").value = cfg.msg_type || "text";
        } else if (channel.channel_type === "feishu") {
            document.getElementById("feishu_webhook_url").value = cfg.webhook_url || "";
            document.getElementById("feishu_secret").value = cfg.secret || "";
            document.getElementById("feishu_msg_type").value = cfg.msg_type || "text";
        } else if (channel.channel_type === "wechat") {
            document.getElementById("wechat_webhook_url").value = cfg.webhook_url || "";
            document.getElementById("wechat_msg_type").value = cfg.msg_type || "text";
        } else if (channel.channel_type === "webhook") {
            document.getElementById("webhook_url").value = cfg.url || "";
            document.getElementById("webhook_method").value = cfg.method || "POST";
            document.getElementById("webhook_headers").value = cfg.headers ? JSON.stringify(cfg.headers) : "";
        } else if (channel.channel_type === "speak") {
            document.getElementById("speak_device_id").value = cfg.device_id || "";
            document.getElementById("speak_volume").value = cfg.volume || "";
            document.getElementById("speak_endvolume").value = cfg.endvolume || "";
            document.getElementById("speak_speed").value = cfg.speed || "1.0";
            document.getElementById("speak_voice_type").value = cfg.voice_type || "female";
        }

        document.getElementById("channelModal").classList.add("active");
    } catch (err) {
        console.error("加载渠道详情失败:", err);
        window.notifications.error("加载渠道配置失败: " + err.message);
    } finally {
        window.loadingManager.hide();
    }
}

/**
 * 校验并构造通道配置 JSON 字典
 */
function buildConfigPayload(type) {
    const config = {};
    if (type === "email") {
        config.smtp_host = document.getElementById("email_smtp_host").value.trim();
        config.smtp_port = parseInt(document.getElementById("email_smtp_port").value) || 465;
        config.smtp_user = document.getElementById("email_smtp_user").value.trim();
        
        const pwd = document.getElementById("email_smtp_password").value;
        if (pwd) {
            config.smtp_password = pwd;
        } // 若编辑状态下不输入密码，则后端根据已有逻辑选择不更新原密码
        
        config.from_address = document.getElementById("email_from_address").value.trim();
        config.to_addresses = document.getElementById("email_to_addresses").value.trim();
        
        if (!config.smtp_host || !config.smtp_user) {
            throw new Error("SMTP 主机及邮箱账号用户名不能为空");
        }
    } else if (type === "dingtalk") {
        config.webhook_url = document.getElementById("dingtalk_webhook_url").value.trim();
        config.secret = document.getElementById("dingtalk_secret").value.trim();
        config.msg_type = document.getElementById("dingtalk_msg_type").value;
        if (!config.webhook_url) throw new Error("机器人 Webhook URL 不能为空");
    } else if (type === "feishu") {
        config.webhook_url = document.getElementById("feishu_webhook_url").value.trim();
        config.secret = document.getElementById("feishu_secret").value.trim();
        config.msg_type = document.getElementById("feishu_msg_type").value;
        if (!config.webhook_url) throw new Error("机器人 Webhook URL 不能为空");
    } else if (type === "wechat") {
        config.webhook_url = document.getElementById("wechat_webhook_url").value.trim();
        config.msg_type = document.getElementById("wechat_msg_type").value;
        if (!config.webhook_url) throw new Error("机器人 Webhook URL 不能为空");
    } else if (type === "webhook") {
        config.url = document.getElementById("webhook_url").value.trim();
        config.method = document.getElementById("webhook_method").value;
        const headersStr = document.getElementById("webhook_headers").value.trim();
        if (headersStr) {
            try {
                config.headers = JSON.parse(headersStr);
            } catch (e) {
                throw new Error("Headers 必须是合法的 JSON 字典格式");
            }
        }
        if (!config.url) throw new Error("回调接口 URL 不能为空");
    } else if (type === "speak") {
        config.device_id = document.getElementById("speak_device_id").value.trim();
        const vol = document.getElementById("speak_volume").value;
        const evol = document.getElementById("speak_endvolume").value;
        if (vol) config.volume = parseInt(vol);
        if (evol) config.endvolume = parseInt(evol);
        config.speed = parseFloat(document.getElementById("speak_speed").value) || 1.0;
        config.voice_type = document.getElementById("speak_voice_type").value;
        if (!config.device_id) throw new Error("播报设备的 Device ID 不能为空");
    }
    return config;
}

/**
 * 提交保存渠道
 */
async function submitChannel() {
    const id = document.getElementById("channelId").value;
    const name = document.getElementById("channelName").value.trim();
    const type = document.getElementById("channelType").value;
    const is_active = document.getElementById("channelActive").checked;

    if (!name || !type) {
        window.notifications.error("名称和类型为必填项");
        return;
    }

    let config = {};
    try {
        config = buildConfigPayload(type);
    } catch (e) {
        window.notifications.error(e.message);
        return;
    }

    const payload = { name, channel_type: type, config, is_active };
    const saveBtn = document.getElementById("saveBtn");

    try {
        saveBtn.disabled = true;
        saveBtn.textContent = "保存中...";

        if (id) {
            // 编辑更新
            await window.apiClient.updateChannel(id, payload);
            window.notifications.success("通道更新成功");
        } else {
            // 新建
            await window.apiClient.createChannel(payload);
            window.notifications.success("通道创建成功");
        }

        closeModal("channelModal");
        loadChannels();
    } catch (err) {
        console.error("保存失败:", err);
        window.notifications.error("保存失败: " + err.message);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = "保存";
    }
}

/**
 * 测试通道链接
 */
async function testChannel(channelId) {
    try {
        window.loadingManager.show();
        const res = await window.apiClient.testChannel(channelId);
        if (res.success) {
            window.notifications.success("测试通知已成功推送到调度任务队列！请注意查收。");
        } else {
            window.notifications.error("发送测试失败: " + res.message);
        }
    } catch (err) {
        console.error("测试通道失败:", err);
        window.notifications.error("发送测试请求出错: " + err.message);
    } finally {
        window.loadingManager.hide();
    }
}

/**
 * 删除通道
 */
function deleteChannel(channelId, channelName) {
    window.modalManager.confirm(
        "确认删除渠道",
        `您确定要删除「${channelName}」这个通知渠道吗？删除后将无法恢复，绑定该渠道的发送可能失效。`,
        async () => {
            try {
                window.loadingManager.show();
                await window.apiClient.deleteChannel(channelId);
                window.notifications.success("渠道删除成功");
                loadChannels();
            } catch (err) {
                console.error("删除渠道失败:", err);
                window.notifications.error("删除失败: " + err.message);
            } finally {
                window.loadingManager.hide();
            }
        }
    );
}
