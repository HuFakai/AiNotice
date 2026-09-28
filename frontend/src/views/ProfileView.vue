<script setup>
/**
 * 个人中心 /profile
 * - 资料：GET/PUT /user/profile（后端当前仅支持 display_name）
 * - 改密：POST /user/change-password；成功后提示「其他设备已强制下线」
 *   （后端递增 token_version，旧 token 失效，故本地也需要重新登录）
 * - 活动记录：GET /user/activities
 * - 登录历史：GET /user/login-history
 * - 统计：GET /user/stats
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import EmptyState from '../components/EmptyState.vue'
import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import {
  changePassword,
  getActivities,
  getLoginHistory,
  getProfile,
  getUserStats,
  updateProfile,
  getLogSettings,
  updateLogSettings,
  runLogCleanup,
} from '../api/user.js'
import {
  activityLabel,
  errorText,
  formatDateTime,
  formatRelative,
  isValidEmail,
  passwordStrength,
} from '../lib/format.js'
import { toastError, toastSuccess } from '../lib/toast.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const router = useRouter()

const loading = ref(true)
const profile = ref(null)
const stats = ref(null)
const activities = ref([])
const history = ref([])

const tab = ref('activities')

/* 资料表单 */
const savingProfile = ref(false)
const profileError = ref('')
const displayName = ref('')

/* 改密表单 */
const pwdForm = ref({ old_password: '', new_password: '', confirm: '' })
const changing = ref(false)
const pwdError = ref('')


/* ---------------- 日志生命周期管理 ---------------- */
const LOG_TABLES = [
  { key: 'api_call_logs', label: 'API 调用日志' },
  { key: 'speak_tasks', label: '播放任务记录' },
  { key: 'user_activities', label: '用户活动记录' },
  { key: 'notification_logs', label: '通知日志' },
]
const logSettings = ref(null)
const logDraft = ref({})
const savingLogs = ref(false)
const logsError = ref('')
const cleaningLogs = ref(false)
const cleanupSummary = ref(null)

async function loadLogSettings() {
  try {
    logSettings.value = await getLogSettings()
    logDraft.value = { ...(logSettings.value?.retentions || {}) }
  } catch (err) {
    logsError.value = errorText(err, '加载日志设置失败')
  }
}

async function saveLogSettings() {
  if (savingLogs.value) return
  logsError.value = ''
  const payload = {}
  for (const t of LOG_TABLES) {
    const v = Number(logDraft.value[t.key])
    if (!Number.isFinite(v) || v < 1 || v > 3650) {
      logsError.value = `${t.label} 的保留天数需在 1-3650 之间`
      return
    }
    payload[t.key] = Math.round(v)
  }
  savingLogs.value = true
  try {
    const data = await updateLogSettings(payload)
    logSettings.value = { ...(logSettings.value || {}), retentions: data.retentions }
    logDraft.value = { ...data.retentions }
    toastSuccess('日志保留天数已更新')
  } catch (err) {
    logsError.value = errorText(err, '保存失败')
  } finally {
    savingLogs.value = false
  }
}

async function runCleanupNow() {
  if (cleaningLogs.value) return
  cleaningLogs.value = true
  cleanupSummary.value = null
  try {
    const data = await runLogCleanup()
    cleanupSummary.value = data?.summary || null
    toastSuccess(data?.message || '清理完成')
    await loadLogSettings()
  } catch (err) {
    toastError(errorText(err, '清理失败'))
  } finally {
    cleaningLogs.value = false
  }
}

loadLogSettings()

const pwdStrength = computed(() => passwordStrength(pwdForm.value.new_password))
const pwdMismatch = computed(
  () => Boolean(pwdForm.value.confirm) && pwdForm.value.new_password !== pwdForm.value.confirm
)
const canChangePwd = computed(
  () =>
    pwdForm.value.old_password.length > 0 &&
    pwdForm.value.new_password.length >= 8 &&
    pwdForm.value.new_password === pwdForm.value.confirm
)

async function load() {
  loading.value = true
  const results = await Promise.allSettled([
    getProfile(),
    getUserStats(),
    getActivities(30, 0),
    getLoginHistory(30, 0),
  ])

  const [pf, st, ac, hi] = results
  if (pf.status === 'fulfilled') {
    profile.value = pf.value
    displayName.value = pf.value?.display_name || ''
  }
  if (st.status === 'fulfilled') stats.value = st.value
  if (ac.status === 'fulfilled') activities.value = ac.value
  if (hi.status === 'fulfilled') history.value = hi.value

  loading.value = false
}

onMounted(load)

/* ---------------- 保存资料 ---------------- */

async function saveProfile() {
  if (savingProfile.value) return
  profileError.value = ''

  const name = displayName.value.trim()
  if (!name) {
    profileError.value = '显示名称不能为空'
    return
  }

  savingProfile.value = true
  try {
    await updateProfile({ display_name: name })
    toastSuccess('资料已更新')

    // 同步到 auth store，顶栏立即反映新名称
    if (profile.value) profile.value = { ...profile.value, display_name: name }
    if (auth.user) auth.setUser({ ...auth.user, display_name: name })
  } catch (err) {
    profileError.value = errorText(err, '保存失败')
  } finally {
    savingProfile.value = false
  }
}

/* ---------------- 修改密码 ---------------- */

async function submitPassword() {
  if (changing.value) return
  pwdError.value = ''

  if (!pwdForm.value.old_password) {
    pwdError.value = '请输入当前密码'
    return
  }
  if (pwdForm.value.new_password.length < 8) {
    pwdError.value = '新密码至少需要 8 位'
    return
  }
  if (pwdForm.value.new_password !== pwdForm.value.confirm) {
    pwdError.value = '两次输入的新密码不一致'
    return
  }
  if (pwdForm.value.new_password === pwdForm.value.old_password) {
    pwdError.value = '新密码不能与当前密码相同'
    return
  }

  changing.value = true
  try {
    await changePassword({
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })

    pwdForm.value = { old_password: '', new_password: '', confirm: '' }
    toastSuccess('密码已修改，其他设备已强制下线，请重新登录')

    // token_version 已递增，当前 token 亦失效 → 清理并回到登录页
    auth.reset()
    setTimeout(() => router.replace({ path: '/login' }), 1200)
  } catch (err) {
    pwdError.value = errorText(err, '修改密码失败，请检查当前密码')
  } finally {
    changing.value = false
  }
}

const activityRows = computed(() => activities.value)
const historyRows = computed(() => history.value)

function activityTone(type) {
  const v = String(type || '').toLowerCase()
  if (v.includes('fail') || v.includes('delete')) return 'error'
  if (v.includes('login') || v.includes('create')) return 'success'
  return 'info'
}
</script>

<template>
  <div class="page">
    <PageHeader
      nav="07"
      eyebrow="PROFILE"
      title="个人中心"
      desc="管理账号资料、登录安全与操作审计记录。"
    >
      <template #actions>
        <button type="button" class="btn btn--ghost btn--sm" :disabled="loading" @click="load">刷新</button>
      </template>
    </PageHeader>

    <div class="stack stagger">
      <!-- 统计 -->
      <div class="grid grid--4">
        <StatCard label="API 调用" :value="stats?.total_api_calls ?? null" hint="累计" />
        <StatCard label="密钥" :value="stats?.api_keys_count ?? null" :hint="`${stats?.active_api_keys ?? 0} 个启用`" />
        <StatCard label="设备" :value="stats?.device_count ?? null" :hint="`${stats?.online_devices ?? 0} 台在线`" />
        <StatCard label="今日播报" :value="stats?.speak_tasks_today ?? null" accent />
      </div>

      <div class="profile-split">
        <!-- 左列：资料 + 改密 -->
        <div class="stack">
          <section class="card">
            <div class="card__head">
              <span class="card__title">
                <span class="led led--active" aria-hidden="true"></span>
                账号资料
              </span>
              <span v-if="profile" class="badge" :class="profile.is_verified ? 'badge--green' : 'badge--warn'">
                {{ profile.is_verified ? '已验证' : '未验证' }}
              </span>
            </div>

            <div v-if="loading" class="loading-row">
              <span class="spinner"></span>
              <span>LOADING</span>
            </div>

            <div v-else class="card__body">
              <div class="dl mb-3">
                <div class="dl__item">
                  <div class="dl__key">用户名</div>
                  <div class="dl__val mono">{{ profile?.username || '—' }}</div>
                </div>
                <div class="dl__item">
                  <div class="dl__key">邮箱</div>
                  <div class="dl__val mono truncate">{{ profile?.email || '—' }}</div>
                </div>
                <div class="dl__item">
                  <div class="dl__key">注册时间</div>
                  <div class="dl__val td-dim">{{ formatDateTime(profile?.created_at) }}</div>
                </div>
                <div class="dl__item">
                  <div class="dl__key">最后登录</div>
                  <div class="dl__val td-dim">{{ formatRelative(profile?.last_login_at) }}</div>
                </div>
              </div>

              <form @submit.prevent="saveProfile">
                <div class="field">
                  <label class="field__label" for="pf-name">显示名称</label>
                  <div class="input-group">
                    <input
                      id="pf-name"
                      v-model="displayName"
                      class="input"
                      type="text"
                      maxlength="100"
                      placeholder="控制台展示用"
                      :disabled="savingProfile"
                    />
                    <button type="submit" class="btn btn--primary" :disabled="savingProfile">
                      <span v-if="savingProfile" class="spinner"></span>
                      <span>{{ savingProfile ? '保存中' : '保存' }}</span>
                    </button>
                  </div>
                  <div class="field__hint">用户名与邮箱不可修改</div>
                </div>

                <div v-if="profileError" class="notice notice--error" role="alert">
                  <span class="led led--error" aria-hidden="true"></span>
                  <span>{{ profileError }}</span>
                </div>
              </form>
            </div>
          </section>

          <section class="card">
            <div class="card__head">
              <span class="card__title">
                <span class="led led--warn" aria-hidden="true"></span>
                修改密码
              </span>
            </div>

            <div class="card__body">
              <div class="notice notice--warn mb-3">
                <span class="led led--warn" aria-hidden="true"></span>
                <span>修改密码后，其它设备上的登录状态会被强制下线，需要重新登录。</span>
              </div>

              <form @submit.prevent="submitPassword">
                <div class="field">
                  <label class="field__label" for="pwd-old">当前密码<span class="req">*</span></label>
                  <input
                    id="pwd-old"
                    v-model="pwdForm.old_password"
                    class="input"
                    type="password"
                    autocomplete="current-password"
                    :disabled="changing"
                  />
                </div>

                <div class="field">
                  <label class="field__label" for="pwd-new">新密码<span class="req">*</span></label>
                  <input
                    id="pwd-new"
                    v-model="pwdForm.new_password"
                    class="input"
                    type="password"
                    autocomplete="new-password"
                    placeholder="至少 8 位"
                    :disabled="changing"
                  />
                  <div class="pw-meter">
                    <div class="pw-meter__bars">
                      <i
                        v-for="i in 5"
                        :key="i"
                        class="pw-meter__bar"
                        :class="i <= pwdStrength.score ? `pw-meter__bar--on-${pwdStrength.level}` : ''"
                      ></i>
                    </div>
                    <span class="pw-meter__text">{{ pwdStrength.level }}</span>
                  </div>
                </div>

                <div class="field">
                  <label class="field__label" for="pwd-confirm">确认新密码<span class="req">*</span></label>
                  <input
                    id="pwd-confirm"
                    v-model="pwdForm.confirm"
                    class="input"
                    :class="{ 'input--invalid': pwdMismatch }"
                    type="password"
                    autocomplete="new-password"
                    :disabled="changing"
                  />
                  <div v-if="pwdMismatch" class="field__error">两次输入的新密码不一致</div>
                </div>

                <div v-if="pwdError" class="notice notice--error mb-3" role="alert">
                  <span class="led led--error" aria-hidden="true"></span>
                  <span>{{ pwdError }}</span>
                </div>

                <button type="submit" class="btn btn--primary btn--block" :disabled="changing || !canChangePwd">
                  <span v-if="changing" class="spinner"></span>
                  <span>{{ changing ? '提交中' : '修改密码' }}</span>
                </button>
              </form>
            </div>
          </section>
          <section class="card">
            <div class="card__head">
              <span class="card__title">
                <span class="led led--info" aria-hidden="true"></span>
                日志生命周期管理
              </span>
            </div>

            <div class="card__body">
              <div class="field__hint" style="margin-bottom: 10px">
                各日志表超过保留天数的数据会在每天 02:00 定时清理，也可点击「立即清理」。当前各表行数实时显示。
              </div>

              <div class="log-life">
                <div v-for="t in LOG_TABLES" :key="t.key" class="log-life__row">
                  <span class="log-life__label">{{ t.label }}</span>
                  <span class="log-life__count mono-dim">{{ logSettings?.counts?.[t.key] ?? '—' }} 行</span>
                  <input
                    v-model="logDraft[t.key]"
                    class="input input--mono log-life__input"
                    type="number"
                    min="1"
                    max="3650"
                    :disabled="savingLogs"
                  />
                  <span class="log-life__unit">天</span>
                </div>
              </div>

              <div v-if="logSettings?.last_cleanup_at" class="field__hint mt-2">
                最近清理：{{ formatDateTime(logSettings.last_cleanup_at) }}
              </div>
              <div v-if="cleanupSummary" class="field__hint">
                本次清理删除 {{ cleanupSummary.total_records_deleted }} 条记录（{{ cleanupSummary.successful_cleanups }} 张表）
              </div>
              <div v-if="logsError" class="notice notice--error mt-2" role="alert">
                <span class="led led--error" aria-hidden="true"></span>
                <span>{{ logsError }}</span>
              </div>

              <div class="row mt-2">
                <button type="button" class="btn btn--primary" :disabled="savingLogs" @click="saveLogSettings">
                  <span v-if="savingLogs" class="spinner"></span>
                  <span>{{ savingLogs ? '保存中' : '保存保留天数' }}</span>
                </button>
                <button type="button" class="btn btn--ghost" :disabled="cleaningLogs" @click="runCleanupNow">
                  <span v-if="cleaningLogs" class="spinner"></span>
                  <span>{{ cleaningLogs ? '清理中' : '立即清理' }}</span>
                </button>
              </div>
            </div>
          </section>

        </div>

        <!-- 右列：活动 / 登录历史 -->
        <section class="card">
          <div class="card__head">
            <div class="segment">
              <button
                type="button"
                class="segment__item"
                :class="{ 'is-active': tab === 'activities' }"
                @click="tab = 'activities'"
              >
                活动记录
              </button>
              <button
                type="button"
                class="segment__item"
                :class="{ 'is-active': tab === 'history' }"
                @click="tab = 'history'"
              >
                登录历史
              </button>
            </div>
            <span class="tag-mono">
              {{ tab === 'activities' ? activityRows.length : historyRows.length }} 条
            </span>
          </div>

          <div v-if="loading" class="loading-row">
            <span class="spinner"></span>
            <span>LOADING</span>
          </div>

          <EmptyState
            v-else-if="tab === 'activities' && !activityRows.length"
            icon="∅"
            title="暂无活动记录"
            desc="创建密钥、绑定账号等操作都会记录在这里。"
          />

          <EmptyState
            v-else-if="tab === 'history' && !historyRows.length"
            icon="∅"
            title="暂无登录历史"
            desc="后续登录会在此留下审计记录。"
          />

          <div v-else class="scrollbox">
            <ul v-if="tab === 'activities'" class="timeline">
              <li v-for="item in activityRows" :key="item.id" class="tl">
                <span class="led" :class="`led--${activityTone(item.activity_type)}`" aria-hidden="true"></span>
                <div class="tl__body">
                  <div class="tl__title">{{ item.activity_description || activityLabel(item.activity_type) }}</div>
                  <div class="tl__meta">
                    <span class="tag-mono">{{ activityLabel(item.activity_type) }}</span>
                    <span v-if="item.client_ip" class="tag-mono mono">{{ item.client_ip }}</span>
                    <span class="tag-mono">{{ formatDateTime(item.created_at) }}</span>
                  </div>
                </div>
              </li>
            </ul>

            <ul v-else class="timeline">
              <li v-for="item in historyRows" :key="item.id" class="tl">
                <span class="led led--info" aria-hidden="true"></span>
                <div class="tl__body">
                  <div class="tl__title">{{ item.activity_description || activityLabel(item.activity_type) }}</div>
                  <div class="tl__meta">
                    <span v-if="item.client_ip" class="tag-mono mono">{{ item.client_ip }}</span>
                    <span class="tag-mono">{{ formatDateTime(item.created_at) }}</span>
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-split {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 1fr);
  gap: 14px;
  align-items: start;
}

@media (max-width: 1020px) {
  .profile-split {
    grid-template-columns: minmax(0, 1fr);
  }
}

.scrollbox {
  max-height: 620px;
  overflow-y: auto;
  padding: 6px 18px 18px;
}

.timeline {
  list-style: none;
  display: flex;
  flex-direction: column;
}

.tl {
  display: flex;
  gap: 11px;
  padding: 11px 0;
  border-bottom: 1px solid var(--line-soft);
}

.tl:last-child {
  border-bottom: none;
}

.tl .led {
  margin-top: 5px;
}

.tl__body {
  min-width: 0;
}

.tl__title {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
}

.tl__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 4px;
}
</style>

<style scoped>
/* 日志生命周期管理 */
.log-life {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-life__row {
  display: grid;
  grid-template-columns: 110px 1fr 110px 34px;
  gap: 10px;
  align-items: center;
}

@media (max-width: 640px) {
  .log-life__row {
    grid-template-columns: 1fr 90px 70px 30px;
  }
}

.log-life__label {
  font-size: 13px;
  color: var(--text);
}

.log-life__count {
  font-size: 12px;
  text-align: right;
}

.log-life__input {
  height: 32px;
}

.log-life__unit {
  font-size: 12px;
  color: var(--text-dim);
}

.mono-dim {
  font-family: var(--font-mono);
  color: var(--text-dim);
}
</style>
