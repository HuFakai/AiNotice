/**
 * 认证状态（Pinia）
 *
 * - token 持久化在 localStorage.auth_token（键名由 api/client.js 统一管理）
 * - user 只放内存，刷新页面后由 fetchMe() 重新拉取，避免读到陈旧资料
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as authApi from '../api/auth.js'
import { clearToken, getToken, setToken } from '../api/client.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken() || '')
  const user = ref(null)
  const loading = ref(false)
  const ready = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))
  const displayName = computed(() => {
    if (!user.value) return '未登录'
    return user.value.display_name || user.value.username || '用户'
  })
  const initials = computed(() => {
    const name = displayName.value
    return name ? name.slice(0, 1).toUpperCase() : '?'
  })
  const isVerified = computed(() => Boolean(user.value?.is_verified))

  function applyToken(value) {
    token.value = value || ''
    if (value) setToken(value)
    else clearToken()
  }

  function setUser(value) {
    user.value = value && typeof value === 'object' ? value : null
  }

  /** 登录：成功后写入 token 与用户信息 */
  async function login(credentials) {
    loading.value = true
    try {
      const data = await authApi.login(credentials)
      const accessToken = data?.access_token
      if (!accessToken) {
        throw new Error('登录响应缺少访问令牌')
      }
      applyToken(accessToken)
      setUser(data?.user || null)

      // 后端未随登录返回用户信息时补拉一次
      if (!user.value) await fetchMe().catch(() => {})
      ready.value = true

      return data
    } finally {
      loading.value = false
    }
  }

  /** 注册（不自动登录，返回后端 message） */
  async function register(payload) {
    loading.value = true
    try {
      return await authApi.register(payload)
    } finally {
      loading.value = false
    }
  }

  /** 拉取当前用户；401 由 client 统一处理 */
  async function fetchMe() {
    if (!token.value) {
      ready.value = true
      return null
    }
    const data = await authApi.me()
    setUser(data)
    ready.value = true
    return data
  }

  /** 本地清理（不调接口） */
  function reset() {
    applyToken('')
    setUser(null)
    ready.value = true
  }

  /** 登出：先通知后端，无论成败都清理本地状态 */
  async function logout() {
    try {
      if (token.value) await authApi.logout()
    } catch {
      /* 忽略：本地状态必须清干净 */
    } finally {
      reset()
    }
  }

  /** 应用启动时恢复会话（有 token 才请求） */
  async function bootstrap() {
    if (!token.value) {
      ready.value = true
      return
    }
    try {
      await fetchMe()
    } catch {
      // token 失效 / 后端不可用：仅在明确 401 时清理，其它情况保留 token 允许重试
      reset()
    }
  }

  return {
    token,
    user,
    loading,
    ready,
    isAuthenticated,
    displayName,
    initials,
    isVerified,
    login,
    register,
    fetchMe,
    logout,
    reset,
    bootstrap,
    setUser,
  }
})
