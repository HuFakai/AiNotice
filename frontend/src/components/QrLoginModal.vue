<script setup>
/**
 * 小米账号扫码登录
 *
 * 流程（严格按 spec 第 5 节）：
 *  1. 打开即 POST /mi-accounts/qr/create → {session_id, qr_image_url, login_url, expires_in}
 *  2. 展示后端代理的 PNG（用 <img :src>，不涉及 innerHTML）。
 *     实现要点：该端点在带鉴权的部署下需要 Authorization 头，而 <img src> 发不出自定义头
 *     （直接绑 src 会 401）。因此优先用带 token 的 fetch 取回二进制转 blob URL 再交给 <img>；
 *     仅当该路径不要求鉴权（fetch 因非鉴权原因失败）时，回退为直接绑定原始 URL。
 *  3. 每 2.5s GET /mi-accounts/qr/{session_id}/status → {status, message, account_id?, mi_username?}
 *  4. confirmed → 成功态（LED 变绿 + 打勾动画），1.5s 后自动关闭并 emit('success')
 *  5. expired / error → 显示重试按钮
 *  6. 组件卸载 / 模态关闭 → 立即停止轮询（并取消在途请求）
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import Modal from './Modal.vue'
import StatusLed from './StatusLed.vue'
import {
  createQrSession,
  fetchQrImage,
  getQrStatus,
  qrImageUrl,
  revokeQrImage,
} from '../api/miAccounts.js'
import { errorText } from '../lib/format.js'
import { toastError, toastSuccess } from '../lib/toast.js'

const props = defineProps({
  open: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'success'])

const POLL_INTERVAL = 2500
const CLOSE_DELAY = 1500

const phase = ref('idle') // idle | loading | waiting | confirmed | expired | error
const sessionId = ref('')
const qrUrl = ref('')
const loginUrl = ref('')
const message = ref('')
const errorMessage = ref('')
const elapsed = ref(0)
const expiresIn = ref(0)
const accountName = ref('')
/** 已创建的 blob URL，需在切换/卸载时释放 */
let qrBlobUrl = ''

let pollTimer = null
let countdownTimer = null
let closeTimer = null
let inFlight = null
let aborted = false

/* ---------------- 轮询控制 ---------------- */

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  if (inFlight && typeof inFlight.abort === 'function') {
    inFlight.abort()
  }
  inFlight = null
}

function stopCloseTimer() {
  if (closeTimer) {
    clearTimeout(closeTimer)
    closeTimer = null
  }
}

function schedulePoll() {
  if (aborted || !sessionId.value) return
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = setTimeout(pollOnce, POLL_INTERVAL)
}

async function pollOnce() {
  if (aborted || !sessionId.value) return

  const controller = new AbortController()
  inFlight = controller

  try {
    const data = await getQrStatus(sessionId.value)
    if (aborted) return

    const status = String(data?.status || 'waiting').toLowerCase()
    message.value = data?.message || ''

    if (status === 'confirmed') {
      accountName.value = data?.mi_username || ''
      phase.value = 'confirmed'
      stopPolling()
      toastSuccess(accountName.value ? `小米账号「${accountName.value}」绑定成功` : '小米账号绑定成功')
      // 成功态停留 1.5s 让用户看到打勾，再关闭并通知父级刷新列表
      stopCloseTimer()
      closeTimer = setTimeout(() => {
        emit('success', { accountId: data?.account_id ?? null, miUsername: accountName.value })
        emit('close')
      }, CLOSE_DELAY)
      return
    }

    if (status === 'expired' || status === 'error') {
      phase.value = status
      errorMessage.value = data?.message || (status === 'expired' ? '二维码已过期' : '扫码登录失败')
      stopPolling()
      return
    }

    // waiting：继续轮询
    phase.value = 'waiting'
    schedulePoll()
  } catch (err) {
    if (aborted || err?.name === 'AbortError') return
    // 单次网络抖动不终止流程：记下提示，继续轮询
    message.value = '网络波动，继续等待…'
    schedulePoll()
  } finally {
    if (inFlight === controller) inFlight = null
  }
}

/* ---------------- 会话创建 ---------------- */

/** 释放上一次的 blob URL，避免内存泄漏 */
function releaseQrBlob() {
  if (qrBlobUrl) {
    revokeQrImage(qrBlobUrl)
    qrBlobUrl = ''
  }
}

/**
 * 加载二维码图片：优先带鉴权 fetch → blob URL；
 * 若该原因失败（例如该端点本就不需要鉴权、或后端未限制），回退直接使用原始 URL。
 */
async function loadQrImage(id, fallbackUrl) {
  releaseQrBlob()
  try {
    const blobUrl = await fetchQrImage(id)
    if (aborted) {
      revokeQrImage(blobUrl)
      return
    }
    qrBlobUrl = blobUrl
    qrUrl.value = blobUrl
  } catch {
    if (aborted) return
    // 回退：直接绑定后端给的地址（不带鉴权的部署仍可显示）
    qrUrl.value = fallbackUrl || qrImageUrl(id)
  }
}

async function start() {
  stopAll()
  aborted = false

  phase.value = 'loading'
  sessionId.value = ''
  qrUrl.value = ''
  loginUrl.value = ''
  message.value = ''
  errorMessage.value = ''
  elapsed.value = 0
  accountName.value = ''
  releaseQrBlob()

  try {
    const data = await createQrSession('')
    if (aborted) return

    sessionId.value = String(data?.session_id || '')
    if (!sessionId.value) throw new Error('服务端未返回会话 ID')

    loginUrl.value = data?.login_url || ''
    expiresIn.value = Number(data?.expires_in) || 0

    phase.value = 'waiting'
    message.value = '请用小米账号 App 扫码'

    countdownTimer = setInterval(() => {
      elapsed.value += 1
    }, 1000)

    // 图片与状态轮询并行启动，任意一个返回快都能让用户尽快看到二维码
    loadQrImage(sessionId.value, data?.qr_image_url)
    schedulePoll()
  } catch (err) {
    if (aborted) return
    phase.value = 'error'
    errorMessage.value = errorText(err, '获取二维码失败，请重试')
    toastError(errorMessage.value)
  }
}

function stopAll() {
  stopPolling()
  stopCloseTimer()
}

/**
 * 二维码 <img> 加载失败：
 * - 仍在等待时，只是图片没取到，保留"等待扫码"语义并继续轮询（用户仍可用备用链接）
 * - 已进入成功/过期态时不再覆盖状态
 */
function onImageError() {
  if (phase.value === 'confirmed' || phase.value === 'expired') return
  phase.value = 'error'
  errorMessage.value = '二维码图片加载失败，请重试'
}

/** 重试：清空旧会话后重新发起 */
function retry() {
  start()
}

/* ---------------- 生命周期 ---------------- */

watch(
  () => props.open,
  (open) => {
    if (open) start()
    else {
      aborted = true
      stopAll()
      releaseQrBlob()
    }
  },
  { immediate: true }
)

// 组件卸载必须停止轮询（spec 明确要求）并释放 blob
onBeforeUnmount(() => {
  aborted = true
  stopAll()
  releaseQrBlob()
})

const remaining = computed(() => {
  if (!expiresIn.value) return null
  return Math.max(0, expiresIn.value - elapsed.value)
})

const statusText = computed(() => {
  if (phase.value === 'loading') return '正在向小米服务器申请二维码…'
  if (phase.value === 'waiting') return message.value || '请用小米账号 App 扫码'
  if (phase.value === 'confirmed') return '登录成功，正在绑定账号…'
  if (phase.value === 'expired') return errorMessage.value || '二维码已过期，请重新获取'
  if (phase.value === 'error') return errorMessage.value || '扫码登录失败'
  return ''
})

const ledTone = computed(() => {
  if (phase.value === 'confirmed') return 'success'
  if (phase.value === 'waiting') return 'warn'
  if (phase.value === 'expired' || phase.value === 'error') return 'error'
  return 'info'
})

const showRetry = computed(() => phase.value === 'expired' || phase.value === 'error')

function onClose() {
  aborted = true
  stopAll()
  releaseQrBlob()
  emit('close')
}
</script>

<template>
  <Modal
    :open="open"
    title="扫码登录小米账号"
    sub="使用小米账号 App 授权，凭据将由服务端加密保存"
    size="sm"
    @close="onClose"
  >
    <div class="qr">
      <!-- 二维码区域 -->
      <div class="qr__stage" :class="`qr__stage--${phase}`">
        <div v-if="phase === 'loading'" class="qr__placeholder">
          <span class="spinner spinner--lg"></span>
        </div>

        <div v-else-if="phase === 'confirmed'" class="qr__success">
          <svg class="qr__check" viewBox="0 0 52 52" aria-hidden="true">
            <circle class="qr__checkCircle" cx="26" cy="26" r="23" fill="none" />
            <path class="qr__checkMark" fill="none" d="M14 27l8 8 16-16" />
          </svg>
        </div>

        <img
          v-else-if="qrUrl"
          class="qr__img"
          :src="qrUrl"
          alt="小米账号登录二维码"
          width="200"
          height="200"
          @error="onImageError"
        />

        <div v-else class="qr__placeholder">
          <span class="tag-mono">NO SIGNAL</span>
        </div>
      </div>

      <!-- 状态行 -->
      <div class="qr__status">
        <StatusLed :tone="ledTone" :pulse="phase === 'waiting' || phase === 'loading'" />
        <span class="qr__statusText">{{ statusText }}</span>
      </div>

      <p v-if="phase === 'waiting' && remaining !== null" class="qr__countdown tag-mono">
        剩余有效期 {{ remaining }}s
      </p>

      <!-- 备用链接：手机浏览器直接打开 -->
      <div v-if="loginUrl && phase !== 'confirmed'" class="qr__alt">
        <span class="tag-mono">备用链接</span>
        <a class="qr__altLink truncate" :href="loginUrl" target="_blank" rel="noopener noreferrer">
          {{ loginUrl }}
        </a>
      </div>

      <p v-if="phase === 'confirmed' && accountName" class="qr__account">
        已绑定账号 <code>{{ accountName }}</code>
      </p>
    </div>

    <template #footer>
      <button v-if="showRetry" type="button" class="btn btn--primary" @click="retry">
        重新获取二维码
      </button>
      <button v-else type="button" class="btn btn--ghost" :disabled="phase === 'confirmed'" @click="onClose">
        取消
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.qr {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 6px 0 2px;
}

.qr__stage {
  display: grid;
  place-items: center;
  width: 214px;
  height: 214px;
  padding: 7px;
  background: #fff;
  border-radius: var(--r-lg);
  border: 1px solid var(--line-strong);
  transition: box-shadow var(--dur) var(--ease), border-color var(--dur) var(--ease);
}

.qr__stage--waiting {
  box-shadow: 0 0 0 4px var(--accent-dim), 0 0 28px -6px rgba(255, 105, 0, 0.45);
  border-color: var(--accent);
}

.qr__stage--confirmed {
  background: var(--well);
  border-color: rgba(61, 220, 151, 0.5);
  box-shadow: 0 0 0 4px var(--green-dim), 0 0 30px -6px rgba(61, 220, 151, 0.5);
}

.qr__stage--expired,
.qr__stage--error {
  border-color: rgba(255, 92, 92, 0.5);
  box-shadow: 0 0 0 4px var(--red-dim);
}

.qr__img {
  display: block;
  width: 200px;
  height: 200px;
  image-rendering: pixelated;
}

.qr__placeholder {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  background: var(--well);
  border-radius: var(--r-md);
}

.qr__success {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
}

/* 打勾动画 */
.qr__check {
  width: 92px;
  height: 92px;
  stroke: var(--signal-green);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.qr__checkCircle {
  stroke-dasharray: 145;
  stroke-dashoffset: 145;
  animation: qrCircle 480ms var(--ease) forwards;
  opacity: 0.55;
}

.qr__checkMark {
  stroke-dasharray: 40;
  stroke-dashoffset: 40;
  animation: qrMark 340ms var(--ease) 420ms forwards;
}

@keyframes qrCircle {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes qrMark {
  to {
    stroke-dashoffset: 0;
  }
}

.qr__status {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 20px;
}

.qr__statusText {
  font-size: 13px;
  color: var(--text);
}

.qr__countdown {
  color: var(--text-mute);
}

.qr__alt {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 9px 11px;
  background: var(--well);
  border: 1px solid var(--line-soft);
  border-radius: var(--r-md);
}

.qr__altLink {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--info);
}

.qr__account {
  font-size: 12.5px;
  color: var(--text-dim);
}

.qr__account code {
  color: var(--signal-green);
}
</style>
