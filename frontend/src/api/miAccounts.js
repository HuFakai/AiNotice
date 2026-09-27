/**
 * 小米账号接口（含扫码登录）
 */

import { del, get, post, put, request, toList } from './client.js'

export async function listMiAccounts() {
  const data = await get('/mi-accounts')
  return toList(data, 'accounts')
}

export const getMiAccount = (id) => get(`/mi-accounts/${id}`)

/** 密码方式添加账号 */
export const createMiAccountSimplified = (payload) => post('/mi-accounts/simplified', payload)

/** 账号统计：{total_accounts, active_accounts, synced_accounts, total_devices, online_devices} */
export const getMiAccountStats = () => get('/mi-accounts/stats/summary', null, { silent: true })

export const syncMiAccount = (id) => post(`/mi-accounts/${id}/sync`, {})

export const testMiAccount = (id) => post(`/mi-accounts/${id}/test`, {})

export const deleteMiAccount = (id) => del(`/mi-accounts/${id}`)

export const updateMiAccount = (id, payload) => put(`/mi-accounts/${id}`, payload)

export const refreshAccountDevices = (id) => post(`/mi-accounts/${id}/refresh-devices`, {})

export const refreshAllDevices = () => post('/mi-accounts/refresh-all-devices', {})

/* ---------------- 扫码登录 ---------------- */

/**
 * 创建扫码会话
 * → {session_id, qr_image_url, login_url, expires_in}
 * name 可空：后端在扫码确认后用小米用户ID命名账号
 */
export const createQrSession = (name) => post('/mi-accounts/qr/create', name ? { name } : {})

/**
 * 轮询扫码状态
 * → {status: waiting|confirmed|expired|error, message, account_id?, mi_username?}
 */
export const getQrStatus = (sessionId) =>
  get(`/mi-accounts/qr/${encodeURIComponent(sessionId)}/status`, null, { silent: true })

/** 二维码图片地址（后端代理 PNG） */
export const qrImageUrl = (sessionId) =>
  `/api/v1/mi-accounts/qr/${encodeURIComponent(sessionId)}/image`

/**
 * 拉取二维码图片并转为 blob URL。
 *
 * 原因：/mi-accounts/qr/{id}/image 需要 Authorization 头，而 <img src> 无法携带
 * 自定义请求头（直接写 src 会 401）。因此这里用带 token 的 fetch 取回二进制，
 * 再交给 <img :src="blobUrl"> 展示——依然是 img 标签，且不涉及 innerHTML。
 *
 * 调用方负责在不再需要时 revokeQrImage(blobUrl) 释放内存。
 */
export async function fetchQrImage(sessionId) {
  const res = await request(`/mi-accounts/qr/${encodeURIComponent(sessionId)}/image`, {
    raw: true,
    silent: true,
  })

  const blob = await res.blob()
  if (!blob || blob.size === 0) throw new Error('二维码内容为空')
  return URL.createObjectURL(blob)
}

/** 释放 blob URL */
export function revokeQrImage(blobUrl) {
  if (blobUrl && blobUrl.startsWith('blob:')) {
    try {
      URL.revokeObjectURL(blobUrl)
    } catch {
      /* 忽略 */
    }
  }
}
