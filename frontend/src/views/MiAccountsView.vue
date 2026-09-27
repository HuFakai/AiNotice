<script setup>
/**
 * 小米账号 /mi-accounts
 * - 列表：sync_status（pending/success/failed → LED）+ device_count
 * - 扫码登录：QrLoginModal（轮询 2.5s，卸载停止）
 * - 密码添加：POST /mi-accounts/simplified
 * - 每行操作：同步 / 测试 / 删除；详情抽屉展示设备
 */
import { computed, onMounted, ref } from 'vue'

import ConfirmDialog from '../components/ConfirmDialog.vue'
import EmptyState from '../components/EmptyState.vue'
import Modal from '../components/Modal.vue'
import PageHeader from '../components/PageHeader.vue'
import QrLoginModal from '../components/QrLoginModal.vue'
import StatCard from '../components/StatCard.vue'
import StatusLed from '../components/StatusLed.vue'
import {
  createMiAccountSimplified,
  deleteMiAccount,
  getMiAccount,
  getMiAccountStats,
  listMiAccounts,
  syncMiAccount,
  testMiAccount,
} from '../api/miAccounts.js'
import { errorText, formatDateTime, formatRelative } from '../lib/format.js'
import { toastError, toastSuccess } from '../lib/toast.js'

const loading = ref(true)
const accounts = ref([])
const stats = ref(null)

/* 扫码 */
const qrOpen = ref(false)

/* 密码添加 */
const addOpen = ref(false)
const adding = ref(false)
const addError = ref('')
const addForm = ref({ mi_username: '', mi_password: '' })
const showPassword = ref(false)

/* 详情 */
const detailOpen = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

/* 删除 */
const deleteTarget = ref(null)

/* 行内忙碌态：记录正在执行操作的账号 ID */
const busyId = ref(null)

const onlineRatio = computed(() => {
  const total = stats.value?.total_devices ?? 0
  const online = stats.value?.online_devices ?? 0
  return total > 0 ? Math.round((online / total) * 100) : null
})

async function load() {
  loading.value = true
  const [listRes, statsRes] = await Promise.allSettled([listMiAccounts(), getMiAccountStats()])
  if (listRes.status === 'fulfilled') accounts.value = listRes.value
  else toastError(errorText(listRes.reason, '加载小米账号失败'))
  if (statsRes.status === 'fulfilled') stats.value = statsRes.value
  loading.value = false
}

onMounted(load)

/* ---------------- 状态映射 ---------------- */

function syncTone(status) {
  const v = String(status || '').toLowerCase()
  if (v === 'success') return 'success'
  if (v === 'failed') return 'error'
  if (v === 'pending') return 'warn'
  return 'offline'
}

function syncText(status) {
  const v = String(status || '').toLowerCase()
  if (v === 'success') return '已同步'
  if (v === 'failed') return '同步失败'
  if (v === 'pending') return '等待同步'
  return '未知状态'
}

/* ---------------- 行内操作 ---------------- */

async function onSync(account) {
  busyId.value = account.id
  try {
    const data = await syncMiAccount(account.id)
    if (data?.success === false) toastError(data?.message || '同步失败')
    else toastSuccess(data?.message || '同步完成')
    await load()
  } catch (err) {
    toastError(errorText(err, '同步失败'))
  } finally {
    busyId.value = null
  }
}

async function onTest(account) {
  busyId.value = account.id
  try {
    const data = await testMiAccount(account.id)
    if (data?.success) toastSuccess(data?.message || '连接正常')
    else toastError(data?.message || '连接测试失败')
  } catch (err) {
    toastError(errorText(err, '连接测试失败'))
  } finally {
    busyId.value = null
  }
}

async function onViewDetail(account) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getMiAccount(account.id)
  } catch (err) {
    toastError(errorText(err, '加载账号详情失败'))
    detailOpen.value = false
  } finally {
    detailLoading.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  const target = deleteTarget.value
  try {
    await deleteMiAccount(target.id)
    toastSuccess('账号已删除')
    deleteTarget.value = null
    await load()
  } catch (err) {
    toastError(errorText(err, '删除失败'))
  }
}

/* ---------------- 密码添加 ---------------- */

function openAdd() {
  addForm.value = { mi_username: '', mi_password: '' }
  addError.value = ''
  showPassword.value = false
  addOpen.value = true
}

async function submitAdd() {
  if (adding.value) return
  addError.value = ''

  const username = addForm.value.mi_username.trim()
  if (!username) {
    addError.value = '请输入小米账号'
    return
  }
  if (addForm.value.mi_password.length < 6) {
    addError.value = '密码长度不能少于 6 位'
    return
  }

  adding.value = true
  try {
    const data = await createMiAccountSimplified({
      mi_username: username,
      mi_password: addForm.value.mi_password,
    })
    // 密码不留存于前端任何位置
    addForm.value.mi_password = ''
    addOpen.value = false
    toastSuccess(data?.message || '小米账号添加成功')

    if (data?.sync_status === 'pending') {
      // 后端异步同步，稍后再刷新一次
      setTimeout(load, 1800)
    }
    await load()
  } catch (err) {
    addError.value = errorText(err, '添加失败，请检查账号与密码')
  } finally {
    adding.value = false
  }
}

/** 扫码成功 → 刷新列表 */
function onQrSuccess() {
  qrOpen.value = false
  setTimeout(load, 600)
}

function accountDevices(account) {
  return Array.isArray(account?.devices) ? account.devices : []
}
</script>

<template>
  <div class="page">
    <PageHeader
      nav="03"
      eyebrow="MI ACCOUNTS"
      title="小米账号"
      desc="绑定小米账号以发现小爱音箱设备。推荐使用扫码登录，凭据由服务端加密保存。"
    >
      <template #actions>
        <button type="button" class="btn btn--ghost btn--sm" :disabled="loading" @click="load">刷新</button>
        <button type="button" class="btn btn--sm" @click="openAdd">密码添加</button>
        <button type="button" class="btn btn--primary btn--sm" @click="qrOpen = true">扫码登录</button>
      </template>
    </PageHeader>

    <div class="stack stagger">
      <!-- 统计 -->
      <div class="grid grid--4">
        <StatCard label="绑定账号" :value="stats?.total_accounts ?? null" :tone="(stats?.total_accounts ?? 0) > 0 ? 'success' : 'offline'" />
        <StatCard label="启用账号" :value="stats?.active_accounts ?? null" />
        <StatCard label="设备总数" :value="stats?.total_devices ?? null" hint="跨全部账号" />
        <StatCard
          label="在线设备"
          :value="stats?.online_devices ?? null"
          accent
          :hint="onlineRatio === null ? '' : `在线率 ${onlineRatio}%`"
        />
      </div>

      <!-- 列表 -->
      <div v-if="loading" class="card">
        <div class="loading-row">
          <span class="spinner"></span>
          <span>LOADING</span>
        </div>
      </div>

      <div v-else-if="!accounts.length" class="card">
        <EmptyState
          icon="◍"
          title="还没有绑定小米账号"
          desc="扫码登录是最快捷的方式：用小米账号 App 扫描二维码即可完成绑定。"
        >
          <button type="button" class="btn btn--primary" @click="qrOpen = true">立即扫码登录</button>
        </EmptyState>
      </div>

      <div v-else class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>账号</th>
              <th>同步状态</th>
              <th>设备</th>
              <th>启用</th>
              <th>最后同步</th>
              <th style="text-align: right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="account in accounts" :key="account.id">
              <td>
                <div class="acct">
                  <div class="acct__name mono">{{ account.mi_username || '未知账号' }}</div>
                  <div v-if="account.error_message" class="acct__err">{{ account.error_message }}</div>
                </div>
              </td>
              <td>
                <StatusLed :tone="syncTone(account.sync_status)" :label="syncText(account.sync_status)" />
              </td>
              <td class="td-mono">
                {{ account.device_count ?? accountDevices(account).length ?? 0 }}
              </td>
              <td>
                <StatusLed :tone="account.is_active ? 'success' : 'offline'" :label="account.is_active ? '启用' : '停用'" />
              </td>
              <td class="td-dim">{{ account.last_sync_at ? formatRelative(account.last_sync_at) : '从未同步' }}</td>
              <td>
                <div class="td-actions">
                  <button
                    type="button"
                    class="btn btn--ghost btn--sm"
                    :disabled="busyId === account.id"
                    @click="onViewDetail(account)"
                  >
                    详情
                  </button>
                  <button
                    type="button"
                    class="btn btn--ghost btn--sm"
                    :disabled="busyId === account.id"
                    @click="onSync(account)"
                  >
                    {{ busyId === account.id ? '处理中' : '同步' }}
                  </button>
                  <button
                    type="button"
                    class="btn btn--ghost btn--sm"
                    :disabled="busyId === account.id"
                    @click="onTest(account)"
                  >
                    测试
                  </button>
                  <button type="button" class="btn btn--danger btn--sm" @click="deleteTarget = account">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="accounts.length" class="notice notice--info">
        <span class="led led--info" aria-hidden="true"></span>
        <span>同步操作用于从小米云端重新拉取设备列表；「测试」会验证当前凭据是否仍然有效。</span>
      </div>
    </div>

    <!-- ============ 扫码登录 ============ -->
    <QrLoginModal :open="qrOpen" @close="qrOpen = false" @success="onQrSuccess" />

    <!-- ============ 密码添加 ============ -->
    <Modal
      :open="addOpen"
      title="密码添加小米账号"
      sub="凭据将以加密方式保存在服务端"
      @close="addOpen = false"
    >
      <div class="notice notice--warn mb-3">
        <span class="led led--warn" aria-hidden="true"></span>
        <span>密码方式可能需要处理短信验证等情况，成功率低于扫码登录。建议优先使用扫码。</span>
      </div>

      <div class="field">
        <label class="field__label" for="mi-username">小米账号<span class="req">*</span></label>
        <input
          id="mi-username"
          v-model="addForm.mi_username"
          class="input input--mono"
          type="text"
          autocomplete="username"
          placeholder="小米 ID / 手机号 / 邮箱"
          :disabled="adding"
          data-autofocus
        />
      </div>

      <div class="field">
        <label class="field__label" for="mi-password">小米密码<span class="req">*</span></label>
        <div class="input-group">
          <input
            id="mi-password"
            v-model="addForm.mi_password"
            class="input input--mono"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            placeholder="至少 6 位"
            :disabled="adding"
          />
          <button type="button" class="btn btn--ghost btn--sm" @click="showPassword = !showPassword">
            {{ showPassword ? '隐藏' : '显示' }}
          </button>
        </div>
      </div>

      <div v-if="addError" class="notice notice--error" role="alert">
        <span class="led led--error" aria-hidden="true"></span>
        <span>{{ addError }}</span>
      </div>

      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="adding" @click="addOpen = false">取消</button>
        <button type="button" class="btn btn--primary" :disabled="adding" @click="submitAdd">
          <span v-if="adding" class="spinner"></span>
          <span>{{ adding ? '添加中' : '添加账号' }}</span>
        </button>
      </template>
    </Modal>

    <!-- ============ 账号详情 ============ -->
    <Modal
      :open="detailOpen"
      :title="detail?.mi_username || '账号详情'"
      sub="账号下的设备清单"
      size="lg"
      @close="detailOpen = false"
    >
      <div v-if="detailLoading" class="loading-row">
        <span class="spinner"></span>
        <span>LOADING</span>
      </div>

      <template v-else-if="detail">
        <div class="dl">
          <div class="dl__item">
            <div class="dl__key">账号 ID</div>
            <div class="dl__val num">{{ detail.id ?? '—' }}</div>
          </div>
          <div class="dl__item">
            <div class="dl__key">同步状态</div>
            <div class="dl__val">
              <StatusLed :tone="syncTone(detail.sync_status)" :label="syncText(detail.sync_status)" />
            </div>
          </div>
          <div class="dl__item">
            <div class="dl__key">设备数量</div>
            <div class="dl__val num">{{ detail.device_count ?? accountDevices(detail).length ?? 0 }}</div>
          </div>
          <div class="dl__item">
            <div class="dl__key">创建时间</div>
            <div class="dl__val td-dim">{{ formatDateTime(detail.created_at) }}</div>
          </div>
        </div>

        <div class="hr"></div>

        <div v-if="accountDevices(detail).length" class="table-wrap">
          <table class="table table--compact">
            <thead>
              <tr>
                <th>设备名称</th>
                <th>设备 ID</th>
                <th>型号</th>
                <th>状态</th>
                <th>音量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="device in accountDevices(detail)" :key="device.device_id || device.id">
                <td>{{ device.device_name || device.name || '未命名' }}</td>
                <td class="td-mono">{{ device.device_id || '—' }}</td>
                <td class="td-dim">{{ device.device_model || device.model || '—' }}</td>
                <td>
                  <StatusLed
                    :tone="device.is_online ? 'success' : 'offline'"
                    :label="device.is_online ? '在线' : '离线'"
                  />
                </td>
                <td class="td-mono">{{ device.volume ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <EmptyState v-else icon="∅" title="该账号下没有设备" desc="尝试点击「同步」重新从小米云端拉取设备列表。" />
      </template>

      <template #footer>
        <button type="button" class="btn btn--ghost" @click="detailOpen = false">关闭</button>
      </template>
    </Modal>

    <!-- ============ 删除确认 ============ -->
    <ConfirmDialog
      :open="Boolean(deleteTarget)"
      title="删除小米账号"
      :message="`删除后该账号下的设备将无法用于播报，操作不可恢复。\n账号：${deleteTarget?.mi_username || ''}`"
      confirm-text="确认删除"
      @cancel="deleteTarget = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.acct {
  min-width: 0;
}

.acct__name {
  font-size: 13px;
  color: var(--text);
}

.acct__err {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--signal-red);
  max-width: 260px;
}
</style>
