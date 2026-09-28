<script setup>
/**
 * 通知渠道 /channels
 * - channel_type 驱动动态表单（email / dingtalk / feishu / wechat / webhook / speak）
 * - 编辑时：密码/secret 类字段一律留空 + 提示「已配置，留空保持不变」
 *   → 绝不把接口返回的 ****** 掩码回填后提交（后端对空值/****** 自动保留旧值）
 * - 测试：POST /channels/{id}/test 返回真实 {success, message, log_id}，失败红色 toast
 */
import { computed, onMounted, ref } from 'vue'

import ConfirmDialog from '../components/ConfirmDialog.vue'
import EmptyState from '../components/EmptyState.vue'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusLed from '../components/StatusLed.vue'
import {
  CHANNEL_TYPES,
  channelTypeMeta,
  createChannel,
  deleteChannel,
  listChannels,
  testChannel,
  updateChannel,
} from '../api/channels.js'
import { listDevices } from '../api/devices.js'
import { errorText, formatRelative } from '../lib/format.js'
import { toastError, toastSuccess } from '../lib/toast.js'

const MASK = '******'

const loading = ref(true)
const channels = ref([])

/* 新建 / 编辑 */
const editorOpen = ref(false)
const saving = ref(false)
const editorError = ref('')
const editingId = ref(null)
const form = ref(makeEmptyForm())

/* 删除 */
const deleteTarget = ref(null)

/* 测试忙碌与最近结果 */
const testingId = ref(null)
const testResults = ref({})

/* 音箱设备（speak 渠道多选用） */
const speakerDevices = ref([])
const devicesLoading = ref(false)

async function loadDevices() {
  devicesLoading.value = true
  try {
    const all = await listDevices()
    speakerDevices.value = all.filter((d) => /speaker/i.test(d.model || '') || /音箱|小爱/i.test(d.name || ''))
  } catch {
    speakerDevices.value = [] // 拉取失败时允许手动保存旧配置，不阻塞表单
  } finally {
    devicesLoading.value = false
  }
}

function deviceName(id) {
  const d = speakerDevices.value.find((x) => x.device_id === String(id))
  return d ? d.name : `设备 ${id}`
}

function toggleDevice(fieldKey, id, checked) {
  const cur = Array.isArray(form.value.config[fieldKey]) ? [...form.value.config[fieldKey]] : []
  const idx = cur.indexOf(id)
  if (checked && idx === -1) cur.push(id)
  if (!checked && idx !== -1) cur.splice(idx, 1)
  form.value.config[fieldKey] = cur
}

const isEditing = computed(() => editingId.value !== null)
const activeType = computed(() => channelTypeMeta(form.value.channel_type))
const typeFields = computed(() => activeType.value.fields || [])

function makeEmptyForm() {
  return { name: '', channel_type: 'email', config: {}, is_active: true, headersText: '' }
}

async function load() {
  loading.value = true
  try {
    channels.value = await listChannels()
  } catch (err) {
    toastError(errorText(err, '加载通知渠道失败'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  loadDevices()
})

/* ---------------- 表单构造 ---------------- */

function openCreate() {
  const firstType = CHANNEL_TYPES[0].value
  form.value = { name: '', channel_type: firstType, config: {}, is_active: true, headersText: '' }
  editingId.value = null
  editorError.value = ''
  seedDefaults()
  editorOpen.value = true
}

function openEdit(channel) {
  const meta = channelTypeMeta(channel.channel_type)
  const config = {}

  // 关键：掩码值不作为表单值回填，用户不填即保留原值
  const rawConfig = channel?.config && typeof channel.config === 'object' ? channel.config : {}
  Object.entries(rawConfig).forEach(([key, value]) => {
    const field = meta.fields.find((f) => f.key === key)
    if (!field) return
    if (field.secret) return // secret 字段一律留空
    if (key === 'headers' && value && typeof value === 'object') return // headers 单独处理
    config[key] = value
  })

  form.value = {
    name: channel.name || '',
    channel_type: channel.channel_type || meta.value,
    config,
    is_active: Boolean(channel.is_active),
    headersText:
      rawConfig.headers && typeof rawConfig.headers === 'object' && Object.keys(rawConfig.headers).length
        ? formatHeadersForEditing(rawConfig.headers)
        : '',
  }

  editingId.value = channel.id
  editorError.value = ''
  editorOpen.value = true
}

/** headers 回显：掩码值用 ****** 占位，提示用户原值仍在 */
function formatHeadersForEditing(headers) {
  try {
    const cleaned = {}
    Object.entries(headers).forEach(([k, v]) => {
      cleaned[k] = v === MASK ? '' : v
    })
    return JSON.stringify(cleaned, null, 2)
  } catch {
    return ''
  }
}

/** 切换类型时重置配置默认值 */
function seedDefaults() {
  const config = {}
  typeFields.value.forEach((field) => {
    if (field.type === 'boolean') config[field.key] = field.default ?? false
    else if (field.default !== undefined) config[field.key] = field.default
  })
  form.value.config = config
  form.value.headersText = ''
}

function onTypeChange() {
  seedDefaults()
  editorError.value = ''
}

/** 该字段在编辑态下是否已配置（展示「已配置，留空保持不变」） */
function isSecretConfigured(field) {
  if (!isEditing.value || !field.secret) return false
  const channel = channels.value.find((c) => c.id === editingId.value)
  const raw = channel?.config?.[field.key]
  return Boolean(raw && raw !== '')
}

/* ---------------- 保存 ---------------- */

async function submit() {
  if (saving.value) return
  editorError.value = ''

  const name = form.value.name.trim()
  if (!name) {
    editorError.value = '请填写渠道名称'
    return
  }

  const config = {}

  for (const field of typeFields.value) {
    const value = form.value.config[field.key]

    if (field.type === 'boolean') {
      config[field.key] = Boolean(value)
      continue
    }

    if (field.type === 'devices') {
      const ids = Array.isArray(value) ? value.filter(Boolean).map(String) : []
      if (field.required && !ids.length) {
        editorError.value = `请选择${field.label}`
        return
      }
      if (ids.length) config[field.key] = ids
      continue
    }

    if (field.type === 'json') {
      const text = String(form.value.headersText || '').trim()
      if (text) {
        try {
          const parsed = JSON.parse(text)
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            config[field.key] = parsed
          } else {
            editorError.value = `${field.label} 必须是 JSON 对象`
            return
          }
        } catch {
          editorError.value = `${field.label} 不是合法的 JSON`
          return
        }
      }
      continue
    }

    const text = value === undefined || value === null ? '' : String(value).trim()

    if (field.secret) {
      // 留空 = 保持原值；仅当用户真正输入了内容才提交
      if (text && text !== MASK) config[field.key] = text
      else if (!isEditing.value) {
        editorError.value = `请填写${field.label}`
        return
      }
      continue
    }

    if (!text) {
      if (field.required) {
        editorError.value = `请填写${field.label}`
        return
      }
      continue
    }

    if (field.type === 'number') {
      const n = Number(text)
      if (!Number.isFinite(n)) {
        editorError.value = `${field.label} 必须是数字`
        return
      }
      config[field.key] = n
      continue
    }

    config[field.key] = text
  }

  // 新建模式下必填校验兜底
  if (!isEditing.value) {
    for (const field of typeFields.value) {
      if (field.required && (config[field.key] === undefined || config[field.key] === '')) {
        editorError.value = `请填写${field.label}`
        return
      }
    }
  }

  const payload = {
    name,
    channel_type: form.value.channel_type,
    config,
    is_active: form.value.is_active,
  }

  saving.value = true
  try {
    if (isEditing.value) {
      await updateChannel(editingId.value, payload)
      toastSuccess('渠道已更新')
    } else {
      await createChannel(payload)
      toastSuccess('渠道已创建')
    }
    editorOpen.value = false
    await load()
  } catch (err) {
    editorError.value = errorText(err, '保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

/* ---------------- 测试 ---------------- */

async function onTest(channel) {
  testingId.value = channel.id
  try {
    const data = await testChannel(channel.id)
    const result = {
      success: Boolean(data?.success),
      message: data?.message || (data?.success ? '发送成功' : '发送失败'),
      logId: data?.log_id ?? null,
      at: new Date(),
    }
    testResults.value = { ...testResults.value, [channel.id]: result }

    if (result.success) toastSuccess(`「${channel.name}」${result.message}`)
    else toastError(`「${channel.name}」${result.message}`)
  } catch (err) {
    const message = errorText(err, '测试失败')
    testResults.value = {
      ...testResults.value,
      [channel.id]: { success: false, message, logId: null, at: new Date() },
    }
    toastError(`「${channel.name}」${message}`)
  } finally {
    testingId.value = null
  }
}

/* ---------------- 删除 ---------------- */

async function confirmDelete() {
  if (!deleteTarget.value) return
  const target = deleteTarget.value
  try {
    await deleteChannel(target.id)
    toastSuccess('渠道已删除')
    deleteTarget.value = null
    await load()
  } catch (err) {
    toastError(errorText(err, '删除失败'))
  }
}

/* ---------------- 展示辅助 ---------------- */

function typeLabel(type) {
  return channelTypeMeta(type).label
}

/** 渠道配置摘要（脱敏值原样展示，绝不猜字段） */
function configSummary(channel) {
  const meta = channelTypeMeta(channel.channel_type)
  const config = channel?.config && typeof channel.config === 'object' ? channel.config : {}
  const parts = []

  meta.fields.forEach((field) => {
    if (field.type === 'boolean') {
      parts.push(`${field.label}：${config[field.key] ? '是' : '否'}`)
      return
    }
    const value = config[field.key]
    if (value === undefined || value === null || value === '') return
    if (field.type === 'json') {
      const count = typeof value === 'object' ? Object.keys(value).length : 0
      parts.push(`${field.label}：${count} 项`)
      return
    }
    if (field.type === 'devices') {
      const ids = Array.isArray(value) ? value : []
      const names = ids.map((id) => deviceName(id)).join('、')
      parts.push(`${field.label}：${names || `${ids.length} 台`}`)
      return
    }
    parts.push(`${field.label}：${String(value)}`)
  })

  return parts
}

function lastResult(channel) {
  return testResults.value[channel.id] || null
}

/** 渠道是否已配置成功（有 config_error 说明解密失败） */
function channelTone(channel) {
  if (channel?.config_error) return 'error'
  return channel?.is_active ? 'success' : 'offline'
}
</script>

<template>
  <div class="page">
    <PageHeader
      nav="06"
      eyebrow="CHANNELS"
      title="通知渠道"
      desc="配置消息推送目标。测试按钮会真实发送一条测试消息，并以实际结果返回。"
    >
      <template #actions>
        <button type="button" class="btn btn--ghost btn--sm" :disabled="loading" @click="load">刷新</button>
        <button type="button" class="btn btn--primary btn--sm" @click="openCreate">新建渠道</button>
      </template>
    </PageHeader>

    <div class="stack stagger">
      <div class="notice notice--info">
        <span class="led led--info" aria-hidden="true"></span>
        <span>
          敏感字段（密码、密钥、签名）在接口返回中均为掩码。编辑时留空即表示保留原值，
          平台不会把掩码回写覆盖你的真实配置。
        </span>
      </div>

      <div v-if="loading" class="card">
        <div class="loading-row">
          <span class="spinner"></span>
          <span>LOADING</span>
        </div>
      </div>

      <div v-else-if="!channels.length" class="card">
        <EmptyState
          icon="⇄"
          title="还没有通知渠道"
          desc="创建渠道后，可通过统一推送接口把消息发送到邮件、群机器人或音箱。"
        >
          <button type="button" class="btn btn--primary" @click="openCreate">新建渠道</button>
        </EmptyState>
      </div>

      <div v-else class="grid grid--auto">
        <article v-for="channel in channels" :key="channel.id" class="card card--hover">
          <div class="card__head">
            <div class="ch__title">
              <StatusLed :tone="channelTone(channel)" />
              <span class="truncate">{{ channel.name }}</span>
            </div>
            <span class="badge badge--accent">{{ typeLabel(channel.channel_type) }}</span>
          </div>

          <div class="card__body">
            <div v-if="channel.config_error" class="notice notice--error mb-2">
              <span class="led led--error" aria-hidden="true"></span>
              <span>{{ channel.config_error }}</span>
            </div>

            <dl class="kv">
              <div v-for="(line, idx) in configSummary(channel)" :key="idx" class="kv__row">
                <dt class="kv__k">{{ line.split('：')[0] }}</dt>
                <dd class="kv__v mono truncate" :title="line.split('：').slice(1).join('：')">
                  {{ line.split('：').slice(1).join('：') }}
                </dd>
              </div>
              <div v-if="!configSummary(channel).length" class="kv__empty">该类型无需额外配置</div>
            </dl>

            <div class="hr"></div>

            <div class="ch__meta">
              <StatusLed :tone="channel.is_active ? 'success' : 'offline'" :label="channel.is_active ? '已启用' : '已停用'" />
              <span class="tag-mono">更新于 {{ formatRelative(channel.updated_at) }}</span>
            </div>

            <div v-if="lastResult(channel)" class="testResult" :class="lastResult(channel).success ? 'testResult--ok' : 'testResult--bad'">
              <span class="led" :class="lastResult(channel).success ? 'led--success' : 'led--error'"></span>
              <span class="truncate">{{ lastResult(channel).message }}</span>
              <span v-if="lastResult(channel).logId" class="tag-mono">#{{ lastResult(channel).logId }}</span>
            </div>
          </div>

          <div class="card__foot ch__foot">
            <button
              type="button"
              class="btn btn--primary btn--sm"
              :disabled="testingId === channel.id"
              @click="onTest(channel)"
            >
              <span v-if="testingId === channel.id" class="spinner"></span>
              <span>{{ testingId === channel.id ? '发送中' : '测试' }}</span>
            </button>
            <button type="button" class="btn btn--ghost btn--sm" @click="openEdit(channel)">编辑</button>
            <div class="spacer"></div>
            <button type="button" class="btn btn--danger btn--sm" @click="deleteTarget = channel">删除</button>
          </div>
        </article>
      </div>
    </div>

    <!-- ============ 新建 / 编辑 ============ -->
    <Modal
      :open="editorOpen"
      :title="isEditing ? '编辑通知渠道' : '新建通知渠道'"
      :sub="isEditing ? '敏感字段留空表示保持原值' : '选择类型后填写对应配置'"
      size="lg"
      @close="editorOpen = false"
    >
      <div class="grid grid--2">
        <div class="field">
          <label class="field__label" for="ch-name">渠道名称<span class="req">*</span></label>
          <input
            id="ch-name"
            v-model="form.name"
            class="input"
            type="text"
            maxlength="100"
            placeholder="例如：运维告警-钉钉群"
            :disabled="saving"
            data-autofocus
          />
        </div>

        <div class="field">
          <label class="field__label" for="ch-type">渠道类型</label>
          <select
            id="ch-type"
            v-model="form.channel_type"
            class="select"
            :disabled="saving"
            @change="onTypeChange"
          >
            <option v-for="type in CHANNEL_TYPES" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
          <div class="field__hint">{{ activeType.hint }}</div>
        </div>
      </div>

      <div class="hr"></div>

      <div v-if="!typeFields.length" class="notice notice--accent">
        <span class="led led--active" aria-hidden="true"></span>
        <span>「{{ activeType.label }}」无需额外配置，消息会通过已绑定的音箱直接念出。</span>
      </div>

      <template v-else>
        <div class="grid grid--2">
          <div
            v-for="field in typeFields"
            :key="field.key"
            class="field"
            :class="{ 'field--wide': field.wide || field.type === 'json' }"
          >
            <label class="field__label" :for="`ch-${field.key}`">
              {{ field.label }}<span v-if="field.required && !isEditing" class="req">*</span>
            </label>

            <!-- 布尔 -->
            <label v-if="field.type === 'boolean'" class="switch">
              <input v-model="form.config[field.key]" type="checkbox" :disabled="saving" />
              <span class="switch__track"></span>
              <span class="switch__label">{{ form.config[field.key] ? '开启' : '关闭' }}</span>
            </label>

            <!-- 音箱设备多选 -->
            <div v-else-if="field.type === 'devices'" class="device-pick">
              <div v-if="devicesLoading" class="field__hint">音箱设备加载中…</div>
              <div v-else-if="!speakerDevices.length" class="field__hint">
                未发现可用音箱：请先到「小米账号」页绑定账号并同步设备
              </div>
              <template v-else>
                <label v-for="d in speakerDevices" :key="d.device_id" class="device-pick__item">
                  <input
                    type="checkbox"
                    class="checkbox"
                    :checked="Array.isArray(form.config[field.key]) && form.config[field.key].includes(d.device_id)"
                    :disabled="saving"
                    @change="toggleDevice(field.key, d.device_id, $event.target.checked)"
                  />
                  <span class="device-pick__name">{{ d.name }}</span>
                  <span class="led" :class="d.online ? 'led--success' : 'led--offline'" aria-hidden="true"></span>
                  <span class="device-pick__model">{{ d.model }}</span>
                </label>
              </template>
            </div>

            <!-- 下拉 -->
            <select
              v-else-if="field.type === 'select'"
              :id="`ch-${field.key}`"
              v-model="form.config[field.key]"
              class="select"
              :disabled="saving"
            >
              <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
            </select>

            <!-- JSON -->
            <textarea
              v-else-if="field.type === 'json'"
              :id="`ch-${field.key}`"
              v-model="form.headersText"
              class="textarea"
              :placeholder="field.placeholder || '{}'"
              :disabled="saving"
            ></textarea>

            <!-- 密码 -->
            <input
              v-else-if="field.type === 'password'"
              :id="`ch-${field.key}`"
              v-model="form.config[field.key]"
              class="input input--mono"
              type="password"
              autocomplete="new-password"
              :placeholder="isSecretConfigured(field) ? '已配置，留空保持不变' : '请输入'"
              :disabled="saving"
            />

            <!-- 数字 -->
            <input
              v-else-if="field.type === 'number'"
              :id="`ch-${field.key}`"
              v-model="form.config[field.key]"
              class="input input--mono"
              type="number"
              :placeholder="field.placeholder || ''"
              :disabled="saving"
            />

            <!-- 文本 -->
            <input
              v-else
              :id="`ch-${field.key}`"
              v-model="form.config[field.key]"
              class="input"
              type="text"
              :placeholder="field.placeholder || ''"
              :disabled="saving"
            />

            <div v-if="field.secret && isSecretConfigured(field)" class="field__hint field__hint--ok">
              ✓ 已配置，留空保持不变
            </div>
            <div v-else-if="field.hint" class="field__hint">{{ field.hint }}</div>
          </div>
        </div>
      </template>

      <div class="hr"></div>

      <label class="switch">
        <input v-model="form.is_active" type="checkbox" :disabled="saving" />
        <span class="switch__track"></span>
        <span class="switch__label">{{ form.is_active ? '创建后立即启用' : '创建后保持停用' }}</span>
      </label>

      <div v-if="editorError" class="notice notice--error mt-3" role="alert">
        <span class="led led--error" aria-hidden="true"></span>
        <span>{{ editorError }}</span>
      </div>

      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="saving" @click="editorOpen = false">取消</button>
        <button type="button" class="btn btn--primary" :disabled="saving" @click="submit">
          <span v-if="saving" class="spinner"></span>
          <span>{{ saving ? '保存中' : isEditing ? '保存修改' : '创建渠道' }}</span>
        </button>
      </template>
    </Modal>

    <!-- ============ 删除确认 ============ -->
    <ConfirmDialog
      :open="Boolean(deleteTarget)"
      title="删除通知渠道"
      :message="`删除后使用该渠道的推送将失败，操作不可恢复。\n渠道：${deleteTarget?.name || ''}`"
      confirm-text="确认删除"
      @cancel="deleteTarget = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.ch__title {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  font-size: 13.5px;
  font-weight: 500;
}

.kv {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.kv__row {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
}

.kv__k {
  font-size: 11.5px;
  color: var(--text-mute);
}

.kv__v {
  font-size: 11.5px;
  color: var(--text-dim);
}

.kv__empty {
  font-size: 12px;
  color: var(--text-mute);
}

.ch__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.testResult {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 11px;
  padding: 7px 10px;
  border-radius: var(--r-sm);
  border: 1px solid var(--line);
  font-size: 11.5px;
}

.testResult--ok {
  color: var(--signal-green);
  border-color: rgba(61, 220, 151, 0.3);
  background: var(--green-dim);
}

.testResult--bad {
  color: var(--signal-red);
  border-color: rgba(255, 92, 92, 0.3);
  background: var(--red-dim);
}

.ch__foot {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field--wide {
  grid-column: 1 / -1;
}

.field__hint--ok {
  color: var(--signal-green);
}

@media (max-width: 620px) {
  .kv__row {
    grid-template-columns: minmax(0, 1fr);
    gap: 2px;
  }
}
</style>

<style scoped>
/* 音箱设备多选列表 */
.device-pick {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.02);
}

.device-pick__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.device-pick__item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.device-pick__name {
  flex: 1;
  font-size: 13px;
  color: var(--text);
}

.device-pick__model {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-dim);
}
</style>
