/**
 * 爱通知 AiNotice — HTTP 客户端
 *
 * 约定（见 docs/FRONTEND_SPEC.md 第 4 节）：
 * - 统一前缀 /api/v1；token 存 localStorage.auth_token
 * - 自动带 Authorization: Bearer <token>
 * - 错误文案统一取响应体的 detail 或 message
 * - 401：清 token → 跳 /login?redirect=当前路径（同一时刻只跳一次）
 * - redirect 只接受站内路径（以 / 开头且不含 //），防开放重定向
 * - 5xx 统一提示「服务暂时不可用」
 * - 全程使用模板插值渲染，禁止 innerHTML 拼接数据
 */

import { toastError } from '../lib/toast.js'

export const API_BASE = '/api/v1'
export const TOKEN_KEY = 'auth_token'

/* ---------------------------------------------------------------
   导航钩子：由 main.js 注入 router，避免 client ←→ router 循环依赖
   --------------------------------------------------------------- */
let navigateTo = null

export function setNavigator(fn) {
  navigateTo = typeof fn === 'function' ? fn : null
}

/* ---------------------------------------------------------------
   Token 存取
   --------------------------------------------------------------- */

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* 隐私模式下 localStorage 可能不可用，静默降级 */
  }
}

export function clearToken() {
  setToken(null)
}

/* ---------------------------------------------------------------
   自定义错误对象
   --------------------------------------------------------------- */

export class ApiError extends Error {
  constructor(message, { status = 0, data = null, path = '' } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
    this.path = path
  }
}

/** 后端可能返回数组形式的 detail（FastAPI 校验错误），这里拍平成可读文本 */
function normalizeDetail(payload, status) {
  if (payload == null) return ''
  if (typeof payload === 'string') return payload.trim()

  if (Array.isArray(payload)) {
    const parts = payload
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object') {
          const loc = Array.isArray(item.loc) ? item.loc.filter((x) => x !== 'body').join('.') : ''
          const msg = item.msg || item.message || ''
          return loc ? `${loc}: ${msg}` : msg
        }
        return ''
      })
      .filter(Boolean)
    return parts.join('；')
  }

  if (typeof payload === 'object') {
    const direct = payload.detail || payload.message || payload.error
    if (typeof direct === 'string' && direct.trim()) return direct.trim()
    // 兜底：把第一个字符串值作为文案，避免显示 [object Object]
    const first = Object.values(payload).find((v) => typeof v === 'string' && v.trim())
    if (first) return String(first).trim()
    const nested = direct != null ? normalizeDetail(direct, status) : ''
    if (nested) return nested
  }

  return status >= 500 ? '服务暂时不可用' : `请求失败（HTTP ${status}）`
}

/* ---------------------------------------------------------------
   401 防抖：同一时刻只跳转一次
   --------------------------------------------------------------- */

let redirecting = false

/** 只允许站内路径：以 / 开头、不含 //、不含协议 */
export function isSafeInternalPath(path) {
  if (typeof path !== 'string') return false
  if (!path.startsWith('/')) return false
  if (path.startsWith('//')) return false
  if (path.includes('://')) return false
  // 反斜杠可被浏览器当作 / 处理，一并拒绝
  if (path.includes('\\')) return false
  return true
}

function handleUnauthorized() {
  clearToken()
  if (redirecting) return
  redirecting = true

  const current = window.location.pathname + window.location.search
  const target = isSafeInternalPath(current) && !current.startsWith('/login')
    ? `/login?redirect=${encodeURIComponent(current)}`
    : '/login'

  if (navigateTo) {
    navigateTo(target)
    // 给路由一点时间完成跳转，随后解除锁，避免后续误判
    setTimeout(() => {
      redirecting = false
    }, 1200)
  } else {
    window.location.replace(target)
  }
}

/* ---------------------------------------------------------------
   核心请求
   --------------------------------------------------------------- */

/**
 * @param {string} path 以 / 开头的接口路径（不含 /api/v1 前缀）
 * @param {{method?: string, body?: any, auth?: boolean, query?: object,
 *          silent?: boolean, signal?: AbortSignal, raw?: boolean}} [options]
 */
export async function request(path, options = {}) {
  const {
    method = 'GET',
    body,
    auth = true,
    query,
    silent = false,
    signal,
    raw = false,
  } = options

  const url = buildUrl(path, query)
  const headers = { Accept: 'application/json' }

  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  let payload
  if (body !== undefined && body !== null) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(url, { method, headers, body: payload, signal })
  } catch (err) {
    if (err && err.name === 'AbortError') throw err
    const message = '网络连接失败，请检查服务是否可用'
    if (!silent) toastError(message)
    throw new ApiError(message, { status: 0, path })
  }

  // 401 统一处理（登录接口自身失败除外，其错误交由调用方展示）
  if (res.status === 401 && !path.startsWith('/auth/login')) {
    handleUnauthorized()
    throw new ApiError('登录状态已失效，请重新登录', { status: 401, path })
  }

  if (res.status === 204) return null

  if (raw) return res

  const contentType = res.headers.get('content-type') || ''
  let data = null
  if (contentType.includes('application/json')) {
    try {
      data = await res.json()
    } catch {
      data = null
    }
  } else {
    data = await res.text().catch(() => '')
  }

  if (!res.ok) {
    let message = normalizeDetail(data, res.status)
    if (res.status >= 500) message = '服务暂时不可用'
    if (res.status === 429 && !message) message = '请求过于频繁，请稍后再试'

    if (!silent) toastError(message)
    throw new ApiError(message, { status: res.status, data, path })
  }

  return data
}

/** 组装 query，跳过 undefined / null / 空字符串 */
function buildUrl(path, query) {
  const base = path.startsWith('/') ? path : `/${path}`
  const url = `${API_BASE}${base}`
  if (!query) return url

  const sp = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) {
      value.forEach((v) => {
        if (v !== undefined && v !== null && v !== '') sp.append(key, v)
      })
    } else {
      sp.append(key, value)
    }
  })

  const qs = sp.toString()
  return qs ? `${url}?${qs}` : url
}

/* ---------------------------------------------------------------
   语法糖
   --------------------------------------------------------------- */

export const get = (path, query, options = {}) => request(path, { ...options, query })

export const post = (path, body, options = {}) => request(path, { ...options, method: 'POST', body })

export const put = (path, body, options = {}) => request(path, { ...options, method: 'PUT', body })

export const patch = (path, body, options = {}) => request(path, { ...options, method: 'PATCH', body })

export const del = (path, options = {}) => request(path, { ...options, method: 'DELETE' })

/* ---------------------------------------------------------------
   响应结构适配：后端列表接口形态不完全统一，统一在此收敛
   --------------------------------------------------------------- */

/** 取数组：兼容 数组 / {data:[...]} / {items:[...]} / {<key>:[...]} */
export function toList(payload, key) {
  if (Array.isArray(payload)) return payload
  if (!payload || typeof payload !== 'object') return []
  if (Array.isArray(payload.data)) return payload.data
  if (Array.isArray(payload.items)) return payload.items
  if (key && Array.isArray(payload[key])) return payload[key]
  for (const value of Object.values(payload)) {
    if (Array.isArray(value)) return value
  }
  return []
}

/** 取对象：兼容 {data:{...}} 包裹 */
export function toData(payload, fallback = null) {
  if (!payload || typeof payload !== 'object') return fallback
  if (payload.data && typeof payload.data === 'object' && !Array.isArray(payload.data)) {
    return payload.data
  }
  return payload
}

/** 安全取数字（0 是合法值，不做 || 兜底） */
export function numOr(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}
