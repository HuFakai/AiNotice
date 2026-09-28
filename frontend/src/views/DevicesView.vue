<script setup>
/**
 * 设备 /devices
 * - 列表：名称 / 型号 / 在线 LED / 音量 / 所属账号
 * - 音量行内滑杆：POST /speak/{device_id}/volume?volume=N（0 是合法值，绝不 || 兜底）
 * - 播放测试：POST /speak/{device_id} body {text}
 * - 停止：POST /speak/stop?device_id=
 * - 刷新：POST /mi-accounts/refresh-all-devices
 */
import { computed, onMounted, ref } from 'vue'

import EmptyState from '../components/EmptyState.vue'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import StatusLed from '../components/StatusLed.vue'
import {
  listDevices,
  refreshAllDevices,
  speakToDevice,
  stopSpeak,
  setDeviceVolume,
  scanDevices,
} from '../api/devices.js'
import { errorText } from '../lib/format.js'
import { toastError, toastSuccess } from '../lib/toast.js'

const loading = ref(true)
const devices = ref([])
const refreshing = ref(false)
const search = ref('')

/** 音量草稿：deviceId -> number（用户拖动时的本地值，松手后提交） */
const volumeDrafts = ref({})
/** 正在提交音量的设备 ID */
const volumeBusy = ref({})

/* 播报测试 */
const speakOpen = ref(false)
const speakTarget = ref(null)
const speakText = ref('')
const speakMode = ref('text') // text | url
const speakUrl = ref('')
const speaking = ref(false)
const speakError = ref('')

/* 行内停止忙碌态 */
const stoppingId = ref(null)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return devices.value
  return devices.value.filter((d) => {
    return (
      String(d.name || '').toLowerCase().includes(q) ||
      String(d.device_id || '').toLowerCase().includes(q) ||
      String(d.model || '').toLowerCase().includes(q) ||
      String(d.account_name || '').toLowerCase().includes(q)
    )
  })
})

const onlineCount = computed(() => devices.value.filter((d) => d.online === true).length)
const unknownCount = computed(() => devices.value.filter((d) => d.online === null).length)
const accountCount = computed(() => new Set(devices.value.map((d) => d.account_id).filter(Boolean)).size)

async function load() {
  loading.value = true
  try {
    devices.value = await listDevices()
    // 用服务端值初始化音量草稿；仅在字段存在时写入
    const drafts = {}
    devices.value.forEach((d) => {
      if (d.volume !== null && d.volume !== undefined) drafts[d.device_id] = d.volume
    })
    volumeDrafts.value = drafts
  } catch (err) {
    toastError(errorText(err, '加载设备列表失败'))
    devices.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)

/** 读取某设备的展示音量：草稿优先，其次服务端值；0 必须保真 */
function displayVolume(device) {
  const draft = volumeDrafts.value[device.device_id]
  if (draft !== undefined && draft !== null && Number.isFinite(Number(draft))) return Number(draft)
  if (device.volume !== null && device.volume !== undefined && Number.isFinite(Number(device.volume))) {
    return Number(device.volume)
  }
  return 50
}

function onVolumeInput(device, event) {
  const raw = Number(event.target.value)
  if (!Number.isFinite(raw)) return
  volumeDrafts.value = { ...volumeDrafts.value, [device.device_id]: raw }
}

async function commitVolume(device) {
  const value = displayVolume(device)
  if (volumeBusy.value[device.device_id]) return

  volumeBusy.value = { ...volumeBusy.value, [device.device_id]: true }
  try {
    await setDeviceVolume(device.device_id, value)
    // 本地同步服务端新值
    const idx = devices.value.findIndex((d) => d.device_id === device.device_id)
    if (idx !== -1) devices.value[idx] = { ...devices.value[idx], volume: value }
    toastSuccess(`${device.name} 音量已设为 ${value}`)
  } catch (err) {
    toastError(errorText(err, '设置音量失败'))
    // 回滚到服务端已知值
    const idx = devices.value.findIndex((d) => d.device_id === device.device_id)
    if (idx !== -1 && devices.value[idx].volume !== null) {
      volumeDrafts.value = { ...volumeDrafts.value, [device.device_id]: devices.value[idx].volume }
    }
  } finally {
    volumeBusy.value = { ...volumeBusy.value, [device.device_id]: false }
  }
}

/* ---------------- 播报测试 ---------------- */

function openSpeak(device) {
  speakTarget.value = device
  speakText.value = ''
  speakMode.value = 'text'
  speakUrl.value = ''
  speakError.value = ''
  speakOpen.value = true
}

async function submitSpeak() {
  if (speaking.value) return
  speakError.value = ''

  if (speakMode.value === 'text') {
    const text = speakText.value.trim()
    if (!text) {
      speakError.value = '请输入要播报的文字'
      return
    }
    if (text.length > 500) {
      speakError.value = '文字内容不能超过 500 字'
      return
    }
  } else if (!speakUrl.value.trim().startsWith('http')) {
    speakError.value = '请输入以 http(s):// 开头的音频地址'
    return
  }

  speaking.value = true
  try {
    const extra = speakMode.value === 'url' ? { url: speakUrl.value.trim() } : {}
    const data = await speakToDevice(speakTarget.value.device_id, speakText.value.trim() || '播放音频', extra)
    if (data?.success === false) {
      speakError.value = data?.message || '播报失败'
      toastError(speakError.value)
    } else {
      toastSuccess(data?.message || '播报任务已下发')
      speakOpen.value = false
    }
  } catch (err) {
    speakError.value = errorText(err, '播报失败')
  } finally {
    speaking.value = false
  }
}

async function onStop(device) {
  stoppingId.value = device.device_id
  try {
    await stopSpeak({ deviceId: device.device_id })
    toastSuccess(`${device.name} 已停止播报`)
  } catch (err) {
    toastError(errorText(err, '停止播报失败'))
  } finally {
    stoppingId.value = null
  }
}

/* ---------------- 刷新设备 ---------------- */

async function onRefreshAll() {
  refreshing.value = true
  try {
    const data = await refreshAllDevices()
    if (data?.success === false) toastError(data?.message || '刷新失败')
    else toastSuccess(data?.message || '设备列表已刷新')
    await load()
  } catch (err) {
    // 兜底尝试 speak 路由的扫描端点
    try {
      await scanDevices()
      toastSuccess('设备缓存已刷新')
      await load()
    } catch {
      toastError(errorText(err, '刷新设备失败'))
    }
  } finally {
    refreshing.value = false
  }
}

function deviceTone(device) {
  if (device.online === true) return 'success'
  if (device.online === false) return 'error'
  return 'warn'
}

function deviceStateText(device) {
  if (device.online === true) return '在线'
  if (device.online === false) return '离线'
  return '状态未知'
}
</script>

<template>
  <div class="page">
    <PageHeader
      nav="04"
      eyebrow="DEVICES"
      title="设备"
      desc="查看已发现的音箱设备、调节音量并下发播报测试。"
    >
      <template #actions>
        <input
          v-model="search"
          class="input input--mono search"
          type="search"
          placeholder="搜索名称 / ID / 账号"
        />
        <button type="button" class="btn btn--ghost btn--sm" :disabled="refreshing" @click="onRefreshAll">
          <span v-if="refreshing" class="spinner"></span>
          <span>{{ refreshing ? '刷新中' : '刷新设备' }}</span>
        </button>
      </template>
    </PageHeader>

    <div class="stack stagger">
      <div class="grid grid--4">
        <StatCard label="设备总数" :value="devices.length" />
        <StatCard label="在线" :value="onlineCount" tone="success" />
        <StatCard
          label="离线"
          :value="Math.max(0, devices.length - onlineCount - unknownCount)"
          :tone="devices.length - onlineCount - unknownCount > 0 ? 'error' : 'offline'"
        />
        <StatCard label="所属账号" :value="accountCount" accent />
      </div>

      <div v-if="loading" class="card">
        <div class="loading-row">
          <span class="spinner"></span>
          <span>LOADING</span>
        </div>
      </div>

      <div v-else-if="!devices.length" class="card">
        <EmptyState
          icon="◉"
          title="尚未发现设备"
          desc="请先在「小米账号」页绑定账号并同步，设备会自动出现在这里。"
        >
          <RouterLink to="/mi-accounts" class="btn btn--primary">前往绑定账号</RouterLink>
        </EmptyState>
      </div>

      <div v-else-if="!filtered.length" class="card">
        <EmptyState icon="⌕" title="没有匹配的设备" :desc="`没有名称或 ID 包含「${search}」的设备。`" />
      </div>

      <div v-else class="grid grid--auto">
        <article v-for="device in filtered" :key="device.device_id" class="card card--hover">
          <div class="card__head">
            <div class="dev__title">
              <StatusLed :tone="deviceTone(device)" />
              <span class="truncate">{{ device.name }}</span>
            </div>
            <span class="badge" :class="`badge--${deviceTone(device)}`">{{ deviceStateText(device) }}</span>
          </div>

          <div class="card__body">
            <div class="dl">
              <div class="dl__item">
                <div class="dl__key">设备 ID</div>
                <div class="dl__val mono truncate">{{ device.device_id || '—' }}</div>
              </div>
              <div class="dl__item">
                <div class="dl__key">型号</div>
                <div class="dl__val td-dim">{{ device.model || '—' }}</div>
              </div>
              <div class="dl__item">
                <div class="dl__key">位置</div>
                <div class="dl__val td-dim">{{ device.location || '未设置' }}</div>
              </div>
              <div class="dl__item">
                <div class="dl__key">所属账号</div>
                <div class="dl__val td-dim truncate">{{ device.account_name || device.account_id || '—' }}</div>
              </div>
            </div>

            <div class="hr"></div>

            <!-- 音量：0 是合法值 -->
            <div class="vol">
              <div class="vol__head">
                <span class="vol__label tag-mono">音量</span>
                <span class="vol__value num">
                  {{ displayVolume(device) }}
                  <span v-if="volumeBusy[device.device_id]" class="spinner" style="width: 11px; height: 11px"></span>
                </span>
              </div>
              <input
                class="slider"
                type="range"
                min="0"
                max="100"
                step="1"
                :value="displayVolume(device)"
                :disabled="Boolean(volumeBusy[device.device_id])"
                :aria-label="`${device.name} 音量`"
                @input="onVolumeInput(device, $event)"
                @change="commitVolume(device)"
              />
              <div class="vol__scale">
                <span>0</span>
                <span>50</span>
                <span>100</span>
              </div>
            </div>
          </div>

          <div class="card__foot dev__foot">
            <button
              type="button"
              class="btn btn--primary btn--sm"
              :disabled="device.online === false"
              @click="openSpeak(device)"
            >
              播放测试
            </button>
            <button
              type="button"
              class="btn btn--ghost btn--sm"
              :disabled="device.online === false || stoppingId === device.device_id"
              @click="onStop(device)"
            >
              <span v-if="stoppingId === device.device_id" class="spinner"></span>
              <span>{{ stoppingId === device.device_id ? '停止中' : '停止' }}</span>
            </button>
          </div>
        </article>
      </div>
    </div>

    <!-- 播报测试 -->
    <Modal
      :open="speakOpen"
      title="播放测试"
      :sub="`${speakTarget?.name || ''} · ${speakTarget?.device_id || ''}`"
      size="sm"
      @close="speakOpen = false"
    >
      <div class="field">
        <label class="field__label">播放方式</label>
        <div class="seg" role="tablist">
          <button type="button" class="seg__item" :class="{ 'seg__item--on': speakMode === 'text' }" :disabled="speaking" @click="speakMode = 'text'">文本播报</button>
          <button type="button" class="seg__item" :class="{ 'seg__item--on': speakMode === 'url' }" :disabled="speaking" @click="speakMode = 'url'">音频 URL</button>
        </div>
      </div>

      <div v-if="speakMode === 'text'" class="field">
        <label class="field__label" for="speak-text">播报内容<span class="req">*</span></label>
        <textarea
          id="speak-text"
          v-model="speakText"
          class="textarea"
          maxlength="500"
          placeholder="例如：测试播报，收到请忽略"
          :disabled="speaking"
          data-autofocus
        ></textarea>
        <div class="field__hint">{{ speakText.length }} / 500 字</div>
      </div>

      <div v-else class="field">
        <label class="field__label" for="speak-url">音频地址<span class="req">*</span></label>
        <input
          id="speak-url"
          v-model="speakUrl"
          class="input"
          type="url"
          placeholder="https://example.com/audio.mp3"
          :disabled="speaking"
          data-autofocus
        />
        <div class="field__hint">音箱将直接播放该在线音频（支持 MP3 等）</div>
      </div>

      <div v-if="speakError" class="notice notice--error" role="alert">
        <span class="led led--error" aria-hidden="true"></span>
        <span>{{ speakError }}</span>
      </div>

      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="speaking" @click="speakOpen = false">取消</button>
        <button type="button" class="btn btn--primary" :disabled="speaking || (speakMode === 'text' ? !speakText.trim() : !speakUrl.trim())" @click="submitSpeak">
          <span v-if="speaking" class="spinner"></span>
          <span>{{ speaking ? '下发中' : '开始播报' }}</span>
        </button>
      </template>
    </Modal>
  </div>
</template>

<style scoped>
.search {
  width: 208px;
  height: 32px;
  padding: 0 11px;
  font-size: 12.5px;
}

.dev__title {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  font-size: 13.5px;
  font-weight: 500;
}

.dev__foot {
  display: flex;
  gap: 8px;
}

.vol__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.vol__value {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 17px;
  font-weight: 600;
  color: var(--accent-hover);
  letter-spacing: -0.02em;
}

.vol__scale {
  display: flex;
  justify-content: space-between;
  margin-top: 5px;
  font-family: var(--font-mono);
  font-size: 9.5px;
  color: var(--text-mute);
}

@media (max-width: 920px) {
  .search {
    width: 100%;
  }
}
</style>
