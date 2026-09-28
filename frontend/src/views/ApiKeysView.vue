<script setup>
/**
 * API 密钥 /api-keys
 * - 列表只展示掩码 api_key
 * - 创建响应里的完整密钥仅此一次：弹出「密钥已创建」模态，强制勾选「我已保存」后才能关闭
 * - 权限用开关组编辑（speak / get_devices / manage_devices / stop_speak / set_volume / get_status / send_notify）
 * - 删除走 ConfirmDialog
 */
import { computed, onMounted, ref } from 'vue'

import ConfirmDialog from '../components/ConfirmDialog.vue'
import CopyButton from '../components/CopyButton.vue'
import EmptyState from '../components/EmptyState.vue'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import {
  PERMISSIONS,
  createApiKey,
  defaultPermissions,
  deleteApiKey,
  listApiKeys,
  updateApiKey,
} from '../api/apiKeys.js'
import { listChannels, channelTypeMeta } from '../api/channels.js'
import { errorText, formatDateTime, formatExpiry } from '../lib/format.js'
import { toastError, toastSuccess } from '../lib/toast.js'

const loading = ref(true)
const keys = ref([])

/* ---------------- 创建 ---------------- */
const createOpen = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = ref({
  key_name: '',
  permissions: defaultPermissions(),
  expires_in_days: '',
  usage_limit: '',
  channel_ids: [],
})

/* ---------------- 一次性密钥 ---------------- */
const secretOpen = ref(false)
const createdSecret = ref(null)
const acknowledged = ref(false)

/* ---------------- 编辑 ---------------- */
const editOpen = ref(false)
const editing = ref(false)
const editError = ref('')
const editTarget = ref(null)
const editForm = ref({ key_name: '', permissions: defaultPermissions(), is_active: true, usage_limit: '', channel_ids: [] })

/* ---------------- 通知渠道绑定 ---------------- */
const availableChannels = ref([])
const channelsLoading = ref(false)

async function loadChannels() {
  channelsLoading.value = true
  try {
    availableChannels.value = await listChannels()
  } catch {
    availableChannels.value = []
  } finally {
    channelsLoading.value = false
  }
}

function toggleChannel(formRef, id, checked) {
  const cur = Array.isArray(formRef.channel_ids) ? [...formRef.channel_ids] : []
  const idx = cur.indexOf(id)
  if (checked && idx === -1) cur.push(id)
  if (!checked && idx !== -1) cur.splice(idx, 1)
  formRef.channel_ids = cur
}

function channelName(id) {
  const ch = availableChannels.value.find((c) => c.id === id)
  return ch ? ch.name : `渠道 #${id}`
}

function boundChannels(key) {
  const ids = Array.isArray(key?.channel_ids) ? key.channel_ids : []
  return ids
    .map((id) => {
      const ch = availableChannels.value.find((c) => c.id === id)
      return ch ? { id, name: ch.name, type: ch.channel_type } : { id, name: `渠道 #${id}`, type: '' }
    })
    .filter((x) => x)
}

/* ---------------- 删除 ---------------- */
const deleteTarget = ref(null)

const activeCount = computed(() => keys.value.filter((k) => k?.is_active && k?.is_valid).length)

async function load() {
  loading.value = true
  try {
    keys.value = await listApiKeys()
  } catch (err) {
    toastError(errorText(err, '加载密钥列表失败'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  loadChannels()
})

/* ---------------- 状态文案 ---------------- */

function keyStatus(key) {
  if (!key) return { tone: 'offline', text: '未知' }
  if (key.is_expired) return { tone: 'error', text: '已过期' }
  if (key.is_usage_exceeded) return { tone: 'error', text: '超限' }
  if (!key.is_active) return { tone: 'offline', text: '已禁用' }
  if (key.is_valid) return { tone: 'success', text: '有效' }
  return { tone: 'warn', text: '不可用' }
}

function permissionCount(permissions) {
  if (!permissions || typeof permissions !== 'object') return 0
  return Object.values(permissions).filter(Boolean).length
}

/* ---------------- 创建流程 ---------------- */

function openCreate() {
  createForm.value = {
    key_name: '',
    permissions: defaultPermissions(),
    expires_in_days: '',
    usage_limit: '',
    channel_ids: [],
  }
  createError.value = ''
  createOpen.value = true
}

async function submitCreate() {
  if (creating.value) return
  createError.value = ''

  const name = createForm.value.key_name.trim()
  if (!name) {
    createError.value = '请填写密钥名称'
    return
  }

  const payload = { key_name: name, permissions: { ...createForm.value.permissions } }
  if (Array.isArray(createForm.value.channel_ids)) {
    payload.channel_ids = createForm.value.channel_ids.filter(Boolean)
  }

  const days = Number(createForm.value.expires_in_days)
  if (createForm.value.expires_in_days !== '' && Number.isFinite(days) && days > 0) {
    payload.expires_in_days = Math.min(365, Math.round(days))
  }

  const limit = Number(createForm.value.usage_limit)
  if (createForm.value.usage_limit !== '' && Number.isFinite(limit) && limit > 0) {
    payload.usage_limit = Math.round(limit)
  }

  creating.value = true
  try {
    const data = await createApiKey(payload)
    createOpen.value = false

    // 完整密钥只在本次响应中出现，立即交给一次性模态组件
    createdSecret.value = {
      api_key: data?.api_key || '',
      key_name: data?.key_name || name,
      expires_at: data?.expires_at || null,
      usage_limit: data?.usage_limit ?? null,
    }
    acknowledged.value = false
    secretOpen.value = true

    await load()
  } catch (err) {
    createError.value = errorText(err, '创建失败，请稍后重试')
  } finally {
    creating.value = false
  }
}

/** 强制确认后才允许关闭一次性密钥模态 */
function closeSecret() {
  if (!acknowledged.value) return
  secretOpen.value = false
  createdSecret.value = null
  toastSuccess('密钥已创建，请妥善保管')
}

/* ---------------- 编辑流程 ---------------- */

function openEdit(key) {
  editTarget.value = key
  editForm.value = {
    key_name: key?.key_name || '',
    permissions: { ...defaultPermissions(), ...(key?.permissions || {}) },
    is_active: Boolean(key?.is_active),
    usage_limit: key?.usage_limit ?? '',
    channel_ids: Array.isArray(key?.channel_ids) ? [...key.channel_ids] : [],
  }
  editError.value = ''
  editOpen.value = true
}

async function submitEdit() {
  if (editing.value) return
  editError.value = ''

  const name = editForm.value.key_name.trim()
  if (!name) {
    editError.value = '请填写密钥名称'
    return
  }

  const payload = {
    key_name: name,
    permissions: { ...editForm.value.permissions },
    is_active: editForm.value.is_active,
    channel_ids: Array.isArray(editForm.value.channel_ids) ? editForm.value.channel_ids.filter(Boolean) : [],
  }

  const limit = Number(editForm.value.usage_limit)
  if (editForm.value.usage_limit !== '' && Number.isFinite(limit) && limit > 0) {
    payload.usage_limit = Math.round(limit)
  }

  editing.value = true
  try {
    await updateApiKey(editTarget.value.id, payload)
    toastSuccess('密钥已更新')
    editOpen.value = false
    await load()
  } catch (err) {
    editError.value = errorText(err, '更新失败，请稍后重试')
  } finally {
    editing.value = false
  }
}

/* ---------------- 删除流程 ---------------- */

async function confirmDelete() {
  if (!deleteTarget.value) return
  const target = deleteTarget.value
  try {
    await deleteApiKey(target.id)
    toastSuccess(`密钥「${target.key_name}」已删除`)
    deleteTarget.value = null
    await load()
  } catch (err) {
    toastError(errorText(err, '删除失败'))
  }
}

/* ---------------- 快速启停 ---------------- */

async function toggleActive(key) {
  try {
    await updateApiKey(key.id, { is_active: !key.is_active })
    toastSuccess(key.is_active ? '密钥已禁用' : '密钥已启用')
    await load()
  } catch (err) {
    toastError(errorText(err, '操作失败'))
  }
}
</script>

<template>
  <div class="page">
    <PageHeader
      nav="02"
      eyebrow="API KEYS"
      title="API 密钥"
      desc="密钥用于服务端调用接口。完整密钥仅在创建时展示一次，请立即保存到安全位置。"
    >
      <template #actions>
        <span class="tag-mono">{{ activeCount }} / {{ keys.length }} 有效</span>
        <button type="button" class="btn btn--primary btn--sm" @click="openCreate">创建密钥</button>
      </template>
    </PageHeader>

    <div class="stack stagger">
      <!-- 安全提示 -->
      <div class="notice notice--accent">
        <span class="led led--active" aria-hidden="true"></span>
        <span>
          列表中的密钥为掩码形式（例如 <code class="mono">xai_sk_••••abcd</code>）。平台不以明文存储密钥，
          关闭创建弹窗后将无法再次查看完整密钥。
        </span>
      </div>

      <div v-if="loading" class="card">
        <div class="loading-row">
          <span class="spinner"></span>
          <span>LOADING</span>
        </div>
      </div>

      <div v-else-if="!keys.length" class="card">
        <EmptyState
          icon="⌘"
          title="还没有 API 密钥"
          desc="创建第一个密钥后即可在服务端调用播报、设备与推送接口。"
        >
          <button type="button" class="btn btn--primary" @click="openCreate">创建密钥</button>
        </EmptyState>
      </div>

      <div v-else class="grid grid--auto keylist">
        <article v-for="key in keys" :key="key.id" class="card card--hover keycard">
          <div class="keycard__head">
            <div class="keycard__title">
              <span class="led" :class="`led--${keyStatus(key).tone}`" aria-hidden="true"></span>
              <span class="truncate">{{ key.key_name || '未命名密钥' }}</span>
            </div>
            <span class="badge" :class="`badge--${keyStatus(key).tone}`">{{ keyStatus(key).text }}</span>
          </div>

          <div class="card__body">
            <div class="keycard__secret">
              <code class="chip-key chip-key--accent truncate">{{ key.api_key || '••••••••' }}</code>
              <span class="tag-mono">掩码</span>
            </div>

            <div class="dl mt-3">
              <div class="dl__item">
                <div class="dl__key">权限位</div>
                <div class="dl__val num">{{ permissionCount(key.permissions) }} 项</div>
              </div>
              <div class="dl__item">
                <div class="dl__key">已调用</div>
                <div class="dl__val num">
                  {{ key.usage_count ?? 0 }}<template v-if="key.usage_limit"> / {{ key.usage_limit }}</template>
                </div>
              </div>
              <div class="dl__item">
                <div class="dl__key">最后使用</div>
                <div class="dl__val td-dim">{{ key.last_used_at ? formatDateTime(key.last_used_at) : '从未使用' }}</div>
              </div>
              <div class="dl__item">
                <div class="dl__key">有效期</div>
                <div class="dl__val td-dim">{{ formatExpiry(key.expires_at) }}</div>
              </div>
            </div>

            <div class="keycard__perms">
              <span
                v-for="perm in PERMISSIONS"
                :key="perm.key"
                class="permchip"
                :class="{ 'permchip--on': key.permissions && key.permissions[perm.key] }"
                :title="perm.desc"
              >
                {{ perm.label }}
              </span>
            </div>

            <div v-if="boundChannels(key).length" class="keycard__channels">
              <span class="keycard__channels-label">推送渠道</span>
              <span v-for="ch in boundChannels(key)" :key="ch.id" class="badge badge--info" :title="`渠道 #${ch.id}`">
                {{ ch.name }}
              </span>
            </div>
          </div>

          <div class="card__foot keycard__foot">
            <button type="button" class="btn btn--ghost btn--sm" @click="openEdit(key)">编辑</button>
            <button type="button" class="btn btn--ghost btn--sm" @click="toggleActive(key)">
              {{ key.is_active ? '禁用' : '启用' }}
            </button>
            <div class="spacer"></div>
            <button type="button" class="btn btn--danger btn--sm" @click="deleteTarget = key">删除</button>
          </div>
        </article>
      </div>
    </div>

    <!-- ============ 创建密钥 ============ -->
    <Modal :open="createOpen" title="创建 API 密钥" sub="按最小权限原则勾选所需能力" @close="createOpen = false">
      <div class="field">
        <label class="field__label" for="key-name">密钥名称<span class="req">*</span></label>
        <input
          id="key-name"
          v-model="createForm.key_name"
          class="input"
          type="text"
          maxlength="100"
          placeholder="例如：生产环境-播报服务"
          :disabled="creating"
          data-autofocus
        />
      </div>

      <div class="field">
        <span class="field__label">权限位</span>
        <div class="perm-grid">
          <label v-for="perm in PERMISSIONS" :key="perm.key" class="perm-item">
            <span class="perm-item__text">
              <span class="perm-item__name">{{ perm.key }}</span>
              <span class="perm-item__desc">{{ perm.label }} · {{ perm.desc }}</span>
            </span>
            <span class="switch">
              <input v-model="createForm.permissions[perm.key]" type="checkbox" :disabled="creating" />
              <span class="switch__track"></span>
            </span>
          </label>
        </div>
      </div>

      <div class="field">
        <span class="field__label">绑定通知渠道</span>
        <div class="field__hint" style="margin-bottom:6px">
          可多选。使用该密钥调用 /notify/send 且不指定渠道时，会自动向这里勾选的启用渠道推送
        </div>
        <div v-if="channelsLoading" class="field__hint">渠道列表加载中…</div>
        <div v-else-if="!availableChannels.length" class="field__hint">
          还没有通知渠道：请先到「通知渠道」页创建
        </div>
        <div v-else class="channel-pick">
          <label v-for="ch in availableChannels" :key="ch.id" class="channel-pick__item">
            <input
              type="checkbox"
              class="checkbox"
              :checked="Array.isArray(createForm.channel_ids) && createForm.channel_ids.includes(ch.id)"
              :disabled="creating"
              @change="toggleChannel(createForm, ch.id, $event.target.checked)"
            />
            <span class="channel-pick__name">{{ ch.name }}</span>
            <span class="badge badge--accent">{{ channelTypeMeta(ch.channel_type).label }}</span>
            <span v-if="!ch.is_active" class="badge badge--warn">已禁用</span>
          </label>
        </div>
      </div>

      <div class="grid grid--2">
        <div class="field">
          <label class="field__label" for="key-days">有效期（天）</label>
          <input
            id="key-days"
            v-model="createForm.expires_in_days"
            class="input input--mono"
            type="number"
            min="1"
            max="365"
            placeholder="留空 = 永久"
            :disabled="creating"
          />
          <div class="field__hint">最大 365 天</div>
        </div>

        <div class="field">
          <label class="field__label" for="key-limit">调用上限</label>
          <input
            id="key-limit"
            v-model="createForm.usage_limit"
            class="input input--mono"
            type="number"
            min="1"
            placeholder="留空 = 不限"
            :disabled="creating"
          />
          <div class="field__hint">超出后密钥失效</div>
        </div>
      </div>

      <div v-if="createError" class="notice notice--error" role="alert">
        <span class="led led--error" aria-hidden="true"></span>
        <span>{{ createError }}</span>
      </div>

      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="creating" @click="createOpen = false">取消</button>
        <button type="button" class="btn btn--primary" :disabled="creating" @click="submitCreate">
          <span v-if="creating" class="spinner"></span>
          <span>{{ creating ? '创建中' : '创建密钥' }}</span>
        </button>
      </template>
    </Modal>

    <!-- ============ 一次性完整密钥 ============ -->
    <Modal
      :open="secretOpen"
      title="密钥已创建"
      sub="这是唯一一次展示完整密钥的机会"
      size="md"
      :lock-close="true"
    >
      <div class="secret">
        <div class="notice notice--warn">
          <span class="led led--warn" aria-hidden="true"></span>
          <span>
            请立即复制并保存到密码管理器或服务端环境变量中。关闭本窗口后，平台将无法再次显示该密钥。
          </span>
        </div>

        <div class="secret__box">
          <div class="secret__label tag-mono">完整密钥 · {{ createdSecret?.key_name }}</div>
          <code class="secret__value break-all">{{ createdSecret?.api_key || '（未返回密钥）' }}</code>
          <CopyButton
            :text="createdSecret?.api_key || ''"
            label="复制密钥"
            subject="API 密钥"
            class="mt-2"
          />
        </div>

        <div class="dl">
          <div class="dl__item">
            <div class="dl__key">有效期</div>
            <div class="dl__val td-dim">{{ formatExpiry(createdSecret?.expires_at) }}</div>
          </div>
          <div class="dl__item">
            <div class="dl__key">调用上限</div>
            <div class="dl__val num">{{ createdSecret?.usage_limit ?? '不限' }}</div>
          </div>
        </div>

        <label class="checkline mt-3">
          <input v-model="acknowledged" type="checkbox" />
          <span>我已将完整密钥保存到安全位置，知悉关闭后无法再次查看</span>
        </label>
      </div>

      <template #footer>
        <button type="button" class="btn btn--primary" :disabled="!acknowledged" @click="closeSecret">
          我已保存，关闭
        </button>
      </template>
    </Modal>

    <!-- ============ 编辑密钥 ============ -->
    <Modal :open="editOpen" title="编辑密钥" :sub="editTarget?.key_name" size="lg" @close="editOpen = false">
      <div class="field">
        <label class="field__label" for="edit-key-name">密钥名称</label>
        <input
          id="edit-key-name"
          v-model="editForm.key_name"
          class="input"
          type="text"
          maxlength="100"
          :disabled="editing"
          data-autofocus
        />
      </div>

      <div class="field">
        <span class="field__label">权限位</span>
        <div class="perm-grid">
          <label v-for="perm in PERMISSIONS" :key="perm.key" class="perm-item">
            <span class="perm-item__text">
              <span class="perm-item__name">{{ perm.key }}</span>
              <span class="perm-item__desc">{{ perm.label }}</span>
            </span>
            <span class="switch">
              <input v-model="editForm.permissions[perm.key]" type="checkbox" :disabled="editing" />
              <span class="switch__track"></span>
            </span>
          </label>
        </div>
      </div>

      <div class="field">
        <span class="field__label">绑定通知渠道</span>
        <div class="field__hint" style="margin-bottom:6px">
          可多选。使用该密钥调用 /notify/send 且不指定渠道时，会自动向这里勾选的启用渠道推送
        </div>
        <div v-if="channelsLoading" class="field__hint">渠道列表加载中…</div>
        <div v-else-if="!availableChannels.length" class="field__hint">
          还没有通知渠道：请先到「通知渠道」页创建
        </div>
        <div v-else class="channel-pick">
          <label v-for="ch in availableChannels" :key="ch.id" class="channel-pick__item">
            <input
              type="checkbox"
              class="checkbox"
              :checked="Array.isArray(editForm.channel_ids) && editForm.channel_ids.includes(ch.id)"
              :disabled="editing"
              @change="toggleChannel(editForm, ch.id, $event.target.checked)"
            />
            <span class="channel-pick__name">{{ ch.name }}</span>
            <span class="badge badge--accent">{{ channelTypeMeta(ch.channel_type).label }}</span>
            <span v-if="!ch.is_active" class="badge badge--warn">已禁用</span>
          </label>
        </div>
      </div>

      <div class="grid grid--2">
        <div class="field">
          <label class="field__label" for="edit-key-limit">调用上限</label>
          <input
            id="edit-key-limit"
            v-model="editForm.usage_limit"
            class="input input--mono"
            type="number"
            min="1"
            placeholder="留空 = 不限"
            :disabled="editing"
          />
        </div>

        <div class="field">
          <span class="field__label">状态</span>
          <label class="switch" style="height: 36px">
            <input v-model="editForm.is_active" type="checkbox" :disabled="editing" />
            <span class="switch__track"></span>
            <span class="switch__label">{{ editForm.is_active ? '启用' : '禁用' }}</span>
          </label>
        </div>
      </div>

      <div v-if="editError" class="notice notice--error" role="alert">
        <span class="led led--error" aria-hidden="true"></span>
        <span>{{ editError }}</span>
      </div>

      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="editing" @click="editOpen = false">取消</button>
        <button type="button" class="btn btn--primary" :disabled="editing" @click="submitEdit">
          <span v-if="editing" class="spinner"></span>
          <span>{{ editing ? '保存中' : '保存' }}</span>
        </button>
      </template>
    </Modal>

    <!-- ============ 删除确认 ============ -->
    <ConfirmDialog
      :open="Boolean(deleteTarget)"
      title="删除 API 密钥"
      :message="`删除后使用该密钥的服务将立即失效，且无法恢复。\n密钥：${deleteTarget?.key_name || ''}`"
      confirm-text="确认删除"
      @cancel="deleteTarget = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.keylist {
  align-items: start;
}

.keycard {
  display: flex;
  flex-direction: column;
}

.keycard__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--line-soft);
}

.keycard__title {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  font-size: 13.5px;
  font-weight: 500;
}

.keycard__secret {
  display: flex;
  align-items: center;
  gap: 8px;
}

.keycard__secret .chip-key {
  flex: 1;
  min-width: 0;
}

.keycard__perms {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 13px;
}

.permchip {
  padding: 2px 7px;
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-mute);
  background: var(--well);
}

.permchip--on {
  color: var(--signal-green);
  border-color: rgba(61, 220, 151, 0.34);
  background: var(--green-dim);
}

.keycard__foot {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 7px;
}

/* 一次性密钥展示 */
.secret {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.secret__box {
  padding: 14px;
  background: var(--well);
  border: 1px solid var(--accent-line);
  border-radius: var(--r-md);
  box-shadow: 0 0 0 3px var(--accent-dim);
}

.secret__label {
  margin-bottom: 7px;
  color: var(--accent-hover);
}

.secret__value {
  display: block;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  color: var(--text);
  padding: 9px 11px;
  background: var(--bg-deep);
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  user-select: all;
}

.checkline {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  font-size: 12.5px;
  color: var(--text-dim);
  line-height: 1.6;
  cursor: pointer;
}

.checkline input {
  margin-top: 3px;
  width: 15px;
  height: 15px;
  accent-color: var(--accent);
  flex: none;
}
</style>

<style scoped>
/* 绑定通知渠道多选列表 */
.channel-pick {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.02);
}

.channel-pick__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.channel-pick__item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.channel-pick__name {
  flex: 1;
  font-size: 13px;
  color: var(--text);
}

.keycard__channels {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
}

.keycard__channels-label {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-dim);
}
</style>
