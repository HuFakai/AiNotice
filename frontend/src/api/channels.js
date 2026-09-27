/**
 * 通知渠道接口
 *
 * 安全约定（见 spec 第 5 节）：
 * - 列表/详情返回的 config 已脱敏，敏感值为 "******"；
 * - 更新时：null / 空字符串 / "******" → 后端保留原值，故编辑表单里
 *   密码类字段一律留空并提示「已配置，留空保持不变」，绝不回填掩码后再提交。
 */

import { del, get, post, put, toList } from './client.js'

/** 渠道类型元数据：驱动动态表单与展示 */
export const CHANNEL_TYPES = [
  {
    value: 'email',
    label: '邮件通知',
    hint: '通过 SMTP 发送邮件',
    fields: [
      { key: 'smtp_host', label: 'SMTP 服务器', required: true, placeholder: 'smtp.example.com' },
      { key: 'smtp_port', label: 'SMTP 端口', type: 'number', required: true, placeholder: '465' },
      { key: 'smtp_user', label: 'SMTP 用户名', required: true, placeholder: 'noreply@example.com' },
      { key: 'smtp_password', label: 'SMTP 密码', type: 'password', required: true, secret: true },
      { key: 'from_name', label: '发件人名称', placeholder: '爱通知' },
      { key: 'to_address', label: '收件地址', required: true, placeholder: 'me@example.com' },
      { key: 'smtp_ssl', label: '启用 SSL', type: 'boolean' },
    ],
  },
  {
    value: 'dingtalk',
    label: '钉钉机器人',
    hint: '发送到钉钉群机器人 Webhook',
    fields: [
      { key: 'webhook_url', label: 'Webhook 地址', required: true, placeholder: 'https://oapi.dingtalk.com/robot/send?access_token=...', wide: true },
      { key: 'secret', label: '加签密钥', type: 'password', secret: true, hint: '机器人开启加签时必填' },
    ],
  },
  {
    value: 'feishu',
    label: '飞书机器人',
    hint: '发送到飞书群机器人 Webhook',
    fields: [
      { key: 'webhook_url', label: 'Webhook 地址', required: true, placeholder: 'https://open.feishu.cn/open-apis/bot/v2/hook/...', wide: true },
      { key: 'secret', label: '签名密钥', type: 'password', secret: true, hint: '开启签名校验时必填' },
    ],
  },
  {
    value: 'wechat',
    label: '企业微信机器人',
    hint: '发送到企业微信群机器人',
    fields: [
      { key: 'webhook_url', label: '机器人 Webhook 地址', required: true, placeholder: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...', wide: true },
    ],
  },
  {
    value: 'webhook',
    label: '自定义 Webhook',
    hint: '以 HTTP 请求推送到任意受信任端点',
    fields: [
      { key: 'url', label: '请求地址', required: true, placeholder: 'https://example.com/hook', wide: true },
      { key: 'method', label: '请求方法', type: 'select', options: ['POST', 'PUT', 'GET'], default: 'POST' },
      { key: 'headers', label: '请求头 (JSON)', type: 'json', wide: true, placeholder: '{"Authorization": "Bearer xxx"}' },
    ],
  },
  {
    value: 'speak',
    label: '小爱音箱播报',
    hint: '用已绑定的音箱念出内容，无需额外配置',
    fields: [],
  },
]

export function channelTypeMeta(type) {
  return CHANNEL_TYPES.find((t) => t.value === type) || { value: type, label: type || '未知类型', hint: '', fields: [] }
}

export async function listChannels() {
  const data = await get('/channels')
  return toList(data, 'channels')
}

export const getChannel = (id) => get(`/channels/${id}`)

export const createChannel = (payload) => post('/channels', payload)

export const updateChannel = (id, payload) => put(`/channels/${id}`, payload)

export const deleteChannel = (id) => del(`/channels/${id}`)

/** 真实发送测试；返回 {success, message, log_id} —— 失败也要展示 message */
export const testChannel = (id) => post(`/channels/${id}/test`, {}, { silent: true })
