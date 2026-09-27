/**
 * API 密钥接口
 *
 * 安全约定：列表接口的 api_key 字段是掩码（如 xai_sk_****abcd），只做展示；
 * 创建接口返回的完整明文密钥仅本次响应可见，展示一次后不再留痕。
 */

import { del, get, post, put, toList } from './client.js'

/** 权限位定义（与后端 CreateApiKeyRequest 的合法值保持一致） */
export const PERMISSIONS = [
  { key: 'speak', label: '语音播报', desc: '调用 /speak 让音箱播放文字' },
  { key: 'get_devices', label: '读取设备', desc: '查询账号下的设备列表与状态' },
  { key: 'manage_devices', label: '管理设备', desc: '刷新、扫描设备' },
  { key: 'stop_speak', label: '停止播放', desc: '中断正在进行的播报' },
  { key: 'set_volume', label: '调节音量', desc: '设置设备音量（0-100）' },
  { key: 'get_status', label: '读取状态', desc: '查询播报任务状态' },
  { key: 'send_notify', label: '统一推送', desc: '调用 /notify/send 推送消息' },
]

/** 默认权限集 */
export function defaultPermissions() {
  return {
    speak: true,
    get_devices: true,
    manage_devices: false,
    stop_speak: true,
    set_volume: true,
    get_status: true,
    send_notify: false,
  }
}

export async function listApiKeys() {
  const data = await get('/api-keys')
  return toList(data, 'api_keys')
}

export const createApiKey = (payload) => post('/api-keys', payload)

export const updateApiKey = (id, payload) => put(`/api-keys/${id}`, payload)

export const deleteApiKey = (id) => del(`/api-keys/${id}`)
