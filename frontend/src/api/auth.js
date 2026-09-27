/**
 * 认证相关接口
 */

import { get, post } from './client.js'

/** 登录：{username_or_email, password} → {access_token, token_type, user} */
export const login = (payload) =>
  post('/auth/login', payload, { auth: false, silent: true })

/** 注册：{username, email, password, display_name?} */
export const register = (payload) =>
  post('/auth/register', payload, { auth: false, silent: true })

/** 登出（失败也不阻塞前端清理） */
export const logout = () => post('/auth/logout', {}, { silent: true })

/** 当前用户信息 */
export const me = () => get('/auth/me', null, { silent: true })

/** 兼容旧后端：部分版本用 /auth/verify 校验 token */
export const verify = () => post('/auth/verify', {}, { silent: true })

/** 用户名可用性检查 */
export const checkUsername = (username) =>
  post('/auth/check-username', { username }, { auth: false, silent: true })

/** 邮箱可用性检查 */
export const checkEmail = (email) =>
  post('/auth/check-email', { email }, { auth: false, silent: true })
