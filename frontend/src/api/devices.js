/**
 * 设备接口
 *
 * ⚠️ 实测对齐（重要）：
 * 本后端并没有 /api/v1/devices 路由，设备列表/音量/播报都挂在 speak 路由下：
 *   - GET  /api/v1/speak/devices                  → {success, message, devices:[DeviceInfo], total}
 *   - POST /api/v1/speak/devices/scan             → 强制刷新缓存
 *   - POST /api/v1/speak/{device_id}              → 指定设备播报（body: {text, volume?, endvolume?, ...}）
 *   - POST /api/v1/speak/stop?device_id=&task_id= → 停止播放（query 参数）
 *   - POST /api/v1/speak/{device_id}/volume?volume= → 设置音量（query 参数，0-100，0 合法）
 *
 * 旧 spec 提到的 /devices 与 body 形式音量接口作为兜底保留：当 speak 路由 404
 * 时自动回退，兼容后端后续新增 /devices 的情况。
 */

import { get, post, request, toList } from './client.js'

/** 设备状态归一化：兼容 status 字符串与 is_online 布尔两种形态 */
export function normalizeDevice(raw) {
  if (!raw || typeof raw !== 'object') return null

  let online = null
  if (typeof raw.status === 'string') {
    online = raw.status.toLowerCase() === 'online'
  } else if (typeof raw.is_online === 'boolean') {
    online = raw.is_online
  }

  return {
    device_id: String(raw.device_id ?? raw.id ?? ''),
    name: raw.name || raw.device_name || '小爱设备',
    model: raw.model || raw.device_model || '',
    location: raw.location || '',
    online,
    // 注意：音量 0 是合法值，这里只在字段确实缺失时回退
    volume: Number.isFinite(Number(raw.volume)) ? Number(raw.volume) : null,
    account_id: raw.mi_account_id ?? null,
    account_name: raw.mi_username || raw.account_name || '',
    raw,
  }
}

/**
 * 获取设备列表
 * 主路径 /speak/devices；若后端尚无该端点（404）则回退 /devices 并从各小米账号聚合。
 */
export async function listDevices() {
  try {
    const data = await get('/speak/devices', null, { silent: true })
    const list = toList(data, 'devices')
    return list.map(normalizeDevice).filter(Boolean)
  } catch (err) {
    if (err?.status !== 404) throw err
  }

  // ---- 回退路径 1：/devices ----
  try {
    const data = await get('/devices', null, { silent: true })
    const list = toList(data, 'devices')
    return list.map(normalizeDevice).filter(Boolean)
  } catch (err) {
    if (err?.status !== 404) throw err
  }

  // ---- 回退路径 2：聚合每个小米账号的 /mi-accounts/{id}/devices ----
  return aggregateDevicesFromAccounts()
}

async function aggregateDevicesFromAccounts() {
  const { listMiAccounts } = await import('./miAccounts.js')
  const accounts = await listMiAccounts()
  if (!accounts.length) return []

  const chunks = await Promise.all(
    accounts.map(async (account) => {
      try {
        const devices = await get(`/mi-accounts/${account.id}/devices`, null, { silent: true })
        const list = toList(devices, 'devices')
        return list.map((d) => {
          const normalized = normalizeDevice(d)
          if (normalized) {
            normalized.account_id = account.id
            normalized.account_name = account.mi_username || account.name || ''
          }
          return normalized
        })
      } catch {
        return []
      }
    })
  )

  return chunks.flat().filter(Boolean)
}

/** 强制刷新所有账号设备（SKU 层遍历） */
export const refreshAllDevices = () => post('/mi-accounts/refresh-all-devices', {})

/** 扫描/刷新设备缓存 */
export const scanDevices = () => post('/speak/devices/scan', {}, { silent: true })

/**
 * 设置音量（0-100，0 是合法值）
 * 主路径：query 参数；失败时回退 body 形态。
 */
export async function setDeviceVolume(deviceId, volume) {
  const value = Math.max(0, Math.min(100, Math.round(Number(volume))))
  if (!Number.isFinite(value)) throw new Error('音量必须是 0-100 的数字')

  try {
    return await post(
      `/speak/${encodeURIComponent(deviceId)}/volume?volume=${value}`,
      undefined,
      { silent: true }
    )
  } catch (err) {
    if (err?.status !== 404 && err?.status !== 422) throw err
    // 回退：旧版 /devices/{id}/volume 的 body 形态
    return request(`/devices/${encodeURIComponent(deviceId)}/volume`, {
      method: 'POST',
      body: { volume: value },
      silent: true,
    })
  }
}

/** 指定设备播报文字 */
export const speakToDevice = (deviceId, text, extra = {}) =>
  post(`/speak/${encodeURIComponent(deviceId)}`, { text, ...extra }, { silent: true })

/** 停止播放：主查询参数形态，失败回退 body 形态 */
export async function stopSpeak({ deviceId, taskId } = {}) {
  const sp = new URLSearchParams()
  if (deviceId) sp.set('device_id', deviceId)
  if (taskId) sp.set('task_id', taskId)
  const qs = sp.toString()

  try {
    return await post(`/speak/stop${qs ? `?${qs}` : ''}`, undefined, { silent: true })
  } catch (err) {
    if (err?.status !== 404 && err?.status !== 422) throw err
    return request('/speak/stop', {
      method: 'POST',
      body: { device_id: deviceId, task_id: taskId },
      silent: true,
    })
  }
}

/** 查询播放任务状态 */
export const getSpeakStatus = (taskId) => get(`/speak/status/${encodeURIComponent(taskId)}`, null, { silent: true })
