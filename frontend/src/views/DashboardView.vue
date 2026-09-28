<script setup>
/**
 * 仪表盘 /
 * - 4 张 StatCard：总调用 / 成功率 / 活跃密钥 / 今日调用
 * - 近 7 日调用量：纯 CSS 自绘柱状图（不引图表库）
 * - 实时状态：QPS + 活跃用户 + 系统健康 LED
 * - 最近调用：GET /analytics/call-logs?page_size=8
 *
 * 所有字段都做了容错：后端字段缺失时展示占位符而不是白屏。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import StatusLed from '../components/StatusLed.vue'
import EmptyState from '../components/EmptyState.vue'
import { getCallLogs, getOverview, getRealTime } from '../api/analytics.js'
import { listApiKeys } from '../api/apiKeys.js'
import { getMiAccountStats } from '../api/miAccounts.js'
import { getUserStats } from '../api/user.js'
import { formatMs, formatNumber, formatShort, formatRelative, statusCodeTone } from '../lib/format.js'
import { toastError } from '../lib/toast.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()

const loading = ref(true)
const overview = ref(null)
const realtime = ref(null)
const userStats = ref(null)
const miStats = ref(null)
const apiKeys = ref([])
const recentCalls = ref([])
const lastUpdated = ref(null)

let refreshTimer = null

const totalCalls = computed(() => overview.value?.totalCalls ?? null)
const successRate = computed(() => {
  const v = overview.value?.successRate
  return v === null || v === undefined ? null : Number(v)
})
const activeKeyCount = computed(() => apiKeys.value.filter((k) => k?.is_active && k?.is_valid).length)
const todayCalls = computed(() => {
  // 优先用实时接口的今日窗口，其次用 user/stats 的总调用
  const series = overview.value?.timeSeries || []
  if (series.length) return series[series.length - 1]?.calls ?? null
  return null
})
const totalApiCalls = computed(() => userStats.value?.total_api_calls ?? null)

/** 近 7 日柱状图数据（时间序列的最后 7 个点） */
const chartBars = computed(() => {
  const series = (overview.value?.timeSeries || []).slice(-7)
  if (!series.length) return []

  const max = Math.max(...series.map((p) => Number(p.calls) || 0), 1)
  return series.map((point) => ({
    label: formatShort(point.timestamp),
    shortLabel: String(point.timestamp || '').slice(5, 10) || '-',
    calls: Number(point.calls) || 0,
    successCalls: Number(point.successCalls) || 0,
    errorCalls: Number(point.errorCalls) || 0,
    heightPct: Math.max(2, Math.round(((Number(point.calls) || 0) / max) * 100)),
  }))
})

const systemHealth = computed(() => {
  const health = realtime.value?.systemHealth || {}
  return Object.entries(health).map(([key, value]) => ({
    key,
    label: { database: '数据库', api: '接口', cache: '缓存', redis: 'Redis' }[key] || key,
    raw: String(value),
    tone: ['healthy', 'ok', 'up', 'true'].includes(String(value).toLowerCase()) ? 'success' : 'error',
  }))
})

const alerts = computed(() => realtime.value?.alerts || [])

async function loadAll({ silent = false } = {}) {
  if (!silent) loading.value = true

  // 并行拉取；单个失败不影响其它模块渲染
  const results = await Promise.allSettled([
    getOverview('7d'),
    getRealTime(),
    getUserStats(),
    getMiAccountStats(),
    listApiKeys(),
    getCallLogs({ period: '7d', page: 1, pageSize: 8 }),
  ])

  const [ov, rt, us, ms, keys, logs] = results

  if (ov.status === 'fulfilled') overview.value = ov.value
  if (rt.status === 'fulfilled') realtime.value = rt.value
  if (us.status === 'fulfilled') userStats.value = us.value
  if (ms.status === 'fulfilled') miStats.value = ms.value
  if (keys.status === 'fulfilled') apiKeys.value = keys.value
  if (logs.status === 'fulfilled') recentCalls.value = logs.value.rows

  const failures = results.filter((r) => r.status === 'rejected')
  if (failures.length === results.length) {
    toastError('无法加载仪表盘数据，请检查后端服务')
  }

  lastUpdated.value = new Date()
  loading.value = false
}

onMounted(() => {
  loadAll()
  // 实时读数每 30s 自动刷新一次（静默，不打断交互）
  refreshTimer = setInterval(() => loadAll({ silent: true }), 30000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '深夜值守'
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})
</script>

<template>
  <div class="page">
    <PageHeader
      nav="01"
      eyebrow="DASHBOARD"
      :title="`${greeting}，${auth.displayName}`"
      desc="小爱音箱消息推送平台的实时读数与调用概览。"
    >
      <template #actions>
        <span v-if="lastUpdated" class="tag-mono">更新于 {{ formatShort(lastUpdated) }}</span>
        <button type="button" class="btn btn--ghost btn--sm" :disabled="loading" @click="loadAll()">
          <span v-if="loading" class="spinner"></span>
          <span>{{ loading ? '刷新中' : '刷新' }}</span>
        </button>
        <RouterLink to="/api-keys" class="btn btn--primary btn--sm">管理密钥</RouterLink>
      </template>
    </PageHeader>

    <div class="stack stagger">
      <!-- ============ 指标卡 ============ -->
      <div class="grid grid--4">
        <StatCard
          label="总调用"
          :value="totalCalls"
          hint="统计周期内累计请求"
          tone="success"
        />
        <StatCard
          label="今日调用"
          :value="todayCalls"
          accent
          hint="最近一个统计窗口"
        />
        <StatCard
          label="活跃密钥"
          :value="activeKeyCount"
          :tone="activeKeyCount > 0 ? 'success' : 'offline'"
          :hint="`共 ${apiKeys.length} 个密钥`"
        />
        <StatCard
          label="成功率"
          :value="successRate"
          :digits="1"
          unit="%"
          :tone="successRate === null ? '' : successRate >= 99 ? 'success' : successRate >= 95 ? 'warn' : 'error'"
          hint="2xx 响应占比"
        />
      </div>

      <!-- ============ 近 7 日调用量 + 实时状态 ============ -->
      <div class="dash-split">
        <section class="card">
          <div class="card__head">
            <span class="card__title">
              <span class="led led--info" aria-hidden="true"></span>
              近 7 日调用量
            </span>
            <span class="tag-mono">CALLS / DAY</span>
          </div>
          <div class="card__body">
            <div v-if="loading && !chartBars.length" class="loading-row">
              <span class="spinner"></span>
              <span>LOADING</span>
            </div>

            <div v-else-if="chartBars.length" class="bars">
              <div v-for="bar in chartBars" :key="bar.label" class="bars__col">
                <span class="bars__val">{{ bar.calls }}</span>
                <div class="bars__track" :title="`${bar.label}：${bar.calls} 次`">
                  <div class="bars__fill" :style="{ height: `${bar.heightPct}%` }"></div>
                </div>
                <span class="bars__label">{{ bar.label }}</span>
              </div>
            </div>

            <EmptyState
              v-else
              icon="▁▃▅"
              title="暂无调用数据"
              desc="当 API 密钥开始被调用后，这里会显示每日调用量趋势。"
            />
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <span class="card__title">
              <span class="led led--active led--pulse" aria-hidden="true"></span>
              实时状态
            </span>
            <span class="tag-mono">LIVE</span>
          </div>
          <div class="card__body">
            <div class="metric-row">
              <div class="metric">
                <div class="metric__label tag-mono">当前 QPS</div>
                <div class="metric__value num">
                  {{ realtime ? Number(realtime.currentQps ?? 0).toFixed(2) : '—' }}
                </div>
              </div>
              <div class="metric">
                <div class="metric__label tag-mono">活跃用户</div>
                <div class="metric__value num">{{ realtime ? realtime.activeUsers : '—' }}</div>
              </div>
            </div>

            <div class="hr"></div>

            <div class="dl">
              <div class="dl__item">
                <div class="dl__key">累计 API 调用</div>
                <div class="dl__val num">{{ totalApiCalls === null ? '—' : formatNumber(totalApiCalls) }}</div>
              </div>
              <div class="dl__item">
                <div class="dl__key">平均响应</div>
                <div class="dl__val num">
                  {{ overview?.avgResponseTime === null || overview?.avgResponseTime === undefined ? '—' : formatMs(overview.avgResponseTime) }}
                </div>
              </div>
              <div class="dl__item">
                <div class="dl__key">设备在线</div>
                <div class="dl__val num">
                  <template v-if="miStats">
                    {{ miStats.online_devices ?? 0 }} / {{ miStats.total_devices ?? 0 }}
                  </template>
                  <template v-else>—</template>
                </div>
              </div>
              <div class="dl__item">
                <div class="dl__key">绑定账号</div>
                <div class="dl__val num">{{ miStats ? miStats.total_accounts ?? 0 : '—' }}</div>
              </div>
            </div>

            <template v-if="systemHealth.length">
              <div class="hr"></div>
              <div class="health">
                <div v-for="item in systemHealth" :key="item.key" class="health__item">
                  <StatusLed :tone="item.tone" />
                  <span class="health__name">{{ item.label }}</span>
                  <span class="health__raw num">{{ item.raw }}</span>
                </div>
              </div>
            </template>
          </div>
        </section>
      </div>

      <!-- ============ 告警 ============ -->
      <div v-if="alerts.length" class="notice notice--warn">
        <div class="stack stack--sm" style="width: 100%">
          <div v-for="(alert, idx) in alerts" :key="idx" class="alertLine">
            <span
              class="led"
              :class="String(alert?.severity).toLowerCase() === 'critical' ? 'led--error' : 'led--warn'"
            ></span>
            <span>{{ alert?.message || '有配额接近上限' }}</span>
          </div>
        </div>
      </div>

      <!-- ============ 最近调用 ============ -->
      <section class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--info" aria-hidden="true"></span>
            最近调用
          </span>
          <RouterLink to="/analytics" class="btn-link">查看全部 →</RouterLink>
        </div>

        <div v-if="loading && !recentCalls.length" class="loading-row">
          <span class="spinner"></span>
          <span>LOADING</span>
        </div>

        <EmptyState
          v-else-if="!recentCalls.length"
          icon="∅"
          title="暂无调用记录"
          desc="使用 API 密钥调用接口后，记录会出现在这里。"
        />

        <div v-else class="table-wrap table-wrap--plain">
          <table class="table table--compact">
            <thead>
              <tr>
                <th>方法</th>
                <th>端点</th>
                <th>状态</th>
                <th>延迟</th>
                <th>密钥</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in recentCalls" :key="log.id ?? `${log.endpoint}-${log.createdAt}`">
                <td>
                  <span class="method" :class="`method--${String(log.method || 'get').toLowerCase()}`">
                    {{ log.method || 'GET' }}
                  </span>
                </td>
                <td class="td-mono truncate" style="max-width: 260px">{{ log.endpoint }}</td>
                <td>
                  <span class="badge" :class="log.statusCode ? `badge--${statusCodeTone(log.statusCode)}` : ''">
                    {{ log.statusCode ?? '—' }}
                  </span>
                </td>
                <td class="td-mono">{{ log.responseTime === null ? '—' : formatMs(log.responseTime) }}</td>
                <td class="td-dim truncate" style="max-width: 130px">{{ log.apiKeyName || '—' }}</td>
                <td class="td-dim">{{ formatRelative(log.createdAt) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.dash-split {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(300px, 1fr);
  gap: 14px;
}

@media (max-width: 1060px) {
  .dash-split {
    grid-template-columns: minmax(0, 1fr);
  }
}

.table-wrap--plain {
  border: none;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.metric__label {
  margin-bottom: 4px;
}

.metric__value {
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--accent-hover);
}

.health {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 9px;
}

.health__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: var(--well);
  border: 1px solid var(--line-soft);
  border-radius: var(--r-md);
}

.health__name {
  font-size: 12.5px;
  color: var(--text-dim);
}

.health__raw {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-mute);
}

.alertLine {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
