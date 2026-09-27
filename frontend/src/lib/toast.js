/**
 * 爱通知 AiNotice — Toast 轻提示（响应式单例）
 *
 * 与具体组件解耦：任何模块都能 push，由 components/Toast.vue 负责渲染。
 */

import { reactive } from 'vue'

export const toastState = reactive({
  items: [],
})

let seq = 0

const TITLES = {
  success: '成功',
  error: '出错了',
  warn: '注意',
  info: '提示',
}

/**
 * 推入一条提示
 * @param {string} message 正文
 * @param {'success'|'error'|'warn'|'info'} type
 * @param {{title?: string, duration?: number}} [opts]
 */
export function toast(message, type = 'info', opts = {}) {
  const text = String(message ?? '').trim()
  if (!text) return -1

  const id = ++seq
  const duration = opts.duration ?? (type === 'error' ? 6500 : 3600)

  toastState.items.push({
    id,
    message: text,
    type,
    title: opts.title || TITLES[type] || TITLES.info,
  })

  // 同时最多保留 4 条，避免刷屏
  while (toastState.items.length > 4) {
    toastState.items.shift()
  }

  if (duration > 0) {
    setTimeout(() => dismiss(id), duration)
  }
  return id
}

export function dismiss(id) {
  const idx = toastState.items.findIndex((t) => t.id === id)
  if (idx !== -1) toastState.items.splice(idx, 1)
}

export const toastSuccess = (m, o) => toast(m, 'success', o)
export const toastError = (m, o) => toast(m, 'error', o)
export const toastWarn = (m, o) => toast(m, 'warn', o)
export const toastInfo = (m, o) => toast(m, 'info', o)

/** 供组件使用的组合式入口 */
export function useToast() {
  return { state: toastState, toast, dismiss, toastSuccess, toastError, toastWarn, toastInfo }
}
