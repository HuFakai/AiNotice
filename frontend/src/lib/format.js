/**
 * 爱通知 AiNotice — 通用格式化与工具函数
 *
 * 约定：所有格式化对空值返回占位符（—），不抛异常，字段缺失也不会导致渲染失败。
 */

const PLACEHOLDER = '—'

/** 时间戳 → YYYY-MM-DD HH:mm:ss（本地时区） */
export function formatDateTime(value) {
  const d = toDate(value)
  if (!d) return PLACEHOLDER
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}:${pad(d.getSeconds())}`
}

/** 时间戳 → MM-DD HH:mm */
export function formatShort(value) {
  const d = toDate(value)
  if (!d) return PLACEHOLDER
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 仅日期 YYYY-MM-DD */
export function formatDate(value) {
  const d = toDate(value)
  if (!d) return PLACEHOLDER
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** 时间戳 → HH:mm */
export function formatTime(value) {
  const d = toDate(value)
  if (!d) return PLACEHOLDER
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 相对时间：刚刚 / N 分钟前 / N 小时前 / N 天前 */
export function formatRelative(value) {
  const d = toDate(value)
  if (!d) return PLACEHOLDER
  const diff = Date.now() - d.getTime()
  if (diff < 0) return '刚刚'

  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`

  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`

  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`

  return formatDate(d)
}

/** 数字千分位 */
export function formatNumber(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return PLACEHOLDER
  return n.toLocaleString('zh-CN')
}

/** 大数缩写：1.2K / 3.4M */
export function formatCompact(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return PLACEHOLDER
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

/** 毫秒 → 可读延迟 */
export function formatMs(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return PLACEHOLDER
  if (n >= 1000) return `${(n / 1000).toFixed(2)}s`
  return `${Math.round(n)}ms`
}

/** 字节 → KB/MB */
export function formatBytes(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), units.length - 1)
  const size = n / Math.pow(1024, i)
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** 百分比（入参按 0-100 计） */
export function formatPercent(value, digits = 1) {
  const n = Number(value)
  if (!Number.isFinite(n)) return PLACEHOLDER
  return `${n.toFixed(digits)}%`
}

/** 剩余有效期描述 */
export function formatExpiry(value) {
  const d = toDate(value)
  if (!d) return '永不过期'
  const diff = d.getTime() - Date.now()
  if (diff <= 0) return '已过期'
  const days = Math.floor(diff / 86400000)
  if (days >= 1) return `${days} 天后过期`
  const hours = Math.max(1, Math.floor(diff / 3600000))
  return `${hours} 小时后过期`
}

function toDate(value) {
  if (value === null || value === undefined || value === '') return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/* ---------------- 剪贴板 ---------------- */

/** 复制文本；优先 navigator.clipboard，降级 execCommand（不使用 innerHTML） */
export async function copyText(text) {
  const value = String(text ?? '')
  if (!value) return false

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch {
    /* 继续走降级方案 */
  }

  try {
    const area = document.createElement('textarea')
    area.value = value
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.top = '-9999px'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(area)
    return ok
  } catch {
    return false
  }
}

/** 复制并附带统一 toast 反馈 */
export async function copyWithToast(text, label = '内容') {
  const { toastSuccess, toastError } = await import('./toast.js')
  const ok = await copyText(text)
  if (ok) toastSuccess(`${label}已复制到剪贴板`)
  else toastError('复制失败，请手动选择文本复制')
  return ok
}

/* ---------------- 表单防抖 ---------------- */

/** 防抖：默认 500ms（注册页可用性检查用） */
export function debounce(fn, wait = 500) {
  let timer = null
  const wrapped = (...args) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, wait)
  }
  wrapped.cancel = () => {
    if (timer) clearTimeout(timer)
    timer = null
  }
  return wrapped
}

/** 粘贴时保留原始宽度的等待辅助 */
export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/* ---------------- 状态与文案映射 ---------------- */

/** LED 状态色映射（与 components.css 的 .led--* 对应） */
export function statusTone(value) {
  const v = String(value ?? '').toLowerCase()
  if (['online', 'success', 'successful', 'active', 'enabled', 'healthy', 'ok', 'completed', 'confirmed'].includes(v)) {
    return 'success'
  }
  if (['offline', 'failed', 'error', 'critical', 'expired', 'disabled', 'inactive', 'exceeded'].includes(v)) {
    return 'error'
  }
  if (['pending', 'waiting', 'syncing', 'warning', 'warn', 'partial', 'playing'].includes(v)) {
    return 'warn'
  }
  if (['info', 'unknown', 'idle'].includes(v)) return 'info'
  return 'offline'
}

const UPDATE_LABELS = {
  UPDATE_PASSWORD: '修改密码',
  UPDATE_PROFILE: '更新资料',
  LOGIN: '登录',
  LOGIN_SUCCESS: '登录成功',
  LOGIN_FAILED: '登录失败',
  LOGOUT: '登出',
  REGISTER: '注册',
  CREATE_API_KEY: '创建 API 密钥',
  UPDATE_API_KEY: '更新 API 密钥',
  DELETE_API_KEY: '删除 API 密钥',
  CREATE_MI_ACCOUNT: '添加小米账号',
  DELETE_MI_ACCOUNT: '删除小米账号',
  SYNC_MI_ACCOUNT: '同步小米账号',
  CREATE_CHANNEL: '创建通知渠道',
  UPDATE_CHANNEL: '更新通知渠道',
  DELETE_CHANNEL: '删除通知渠道',
  TEST_CHANNEL: '测试通知渠道',
  SEND_NOTIFICATION: '发送通知',
  SPEAK: '语音播报',
  SET_VOLUME: '设置音量',
  STOP_SPEAK: '停止播报',
}

/** 活动类型 → 中文文案 */
export function activityLabel(type) {
  if (!type) return '未知操作'
  const key = String(type).toUpperCase()
  return UPDATE_LABELS[key] || type
}

/** HTTP 状态码 → 徽章色调 */
export function statusCodeTone(code) {
  const n = Number(code)
  if (!Number.isFinite(n)) return ''
  if (n < 300) return 'green'
  if (n < 400) return 'info'
  if (n < 500) return 'warn'
  return 'red'
}

/** 权限对象 → 中文标签数组 */
export function permissionLabels(permissions) {
  if (!permissions || typeof permissions !== 'object') return []
  const names = {
    speak: '语音播报',
    get_devices: '读取设备',
    manage_devices: '管理设备',
    stop_speak: '停止播放',
    set_volume: '调节音量',
    get_status: '读取状态',
    send_notify: '统一推送',
  }
  return Object.entries(permissions)
    .filter(([, v]) => Boolean(v))
    .map(([k]) => names[k] || k)
}

/** 密码强度（注册 / 改密共用） */
export function passwordStrength(password) {
  const value = String(password || '')
  const checks = {
    minLength: value.length >= 8,
    hasUpper: /[A-Z]/.test(value),
    hasLower: /[a-z]/.test(value),
    hasNumber: /\d/.test(value),
    hasSpecial: /[^A-Za-z0-9]/.test(value),
  }
  const score = Object.values(checks).filter(Boolean).length
  let level = 'weak'
  if (score >= 5) level = 'strong'
  else if (score >= 3) level = 'medium'
  return { score, level, checks }
}

/** 邮箱格式校验（与后端 EmailStr 保持一致的宽口径） */
export function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim())
}

/** 用户名字符集：字母/数字/下划线，3-50 位（与后端校验一致） */
export function isValidUsername(value) {
  const v = String(value || '').trim()
  return v.length >= 3 && v.length <= 50 && /^[A-Za-z0-9_]+$/.test(v)
}

/** 从任意错误对象提取可展示文案 */
export function errorText(err, fallback = '操作失败，请稍后重试') {
  if (!err) return fallback
  if (typeof err === 'string') return err
  return err.message || fallback
}
