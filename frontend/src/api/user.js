/**
 * 用户中心 + 统一推送接口
 */

import { get, post, put, toList } from './client.js'

/** 用户资料 */
export const getProfile = () => get('/user/profile')

/** 更新资料（当前后端仅支持 display_name） */
export const updateProfile = (payload) => put('/user/profile', payload)

/** 修改密码；成功后后端会递增 token_version，使其它设备的旧 token 失效 */
export const changePassword = (payload) => post('/user/change-password', payload)

export async function getActivities(limit = 20, offset = 0) {
  const data = await get('/user/activities', { limit, offset }, { silent: true })
  return toList(data, 'activities')
}

export async function getLoginHistory(limit = 20, offset = 0) {
  const data = await get('/user/login-history', { limit, offset }, { silent: true })
  return toList(data, 'history')
}

/** 用户统计：设备数、密钥数、调用总数等 */
export const getUserStats = () => get('/user/stats', null, { silent: true })

/** 统一推送（异步受理，success 仅代表已入队） */
export const sendNotification = (payload) => post('/notify/send', payload)
