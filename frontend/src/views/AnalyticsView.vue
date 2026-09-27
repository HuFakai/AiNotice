<script setup>
/**
 * 统计分析 /analytics
 * - 周期切换 24h / 7d / 30d（mono 分段控件）
 * - 概览 + 端点 Top（mono 路径 + 请求占比条）+ 延迟 P50/P95/P99
 * - 配额使用情况
 * - 调用日志分页表
 */
import { computed, onMounted, ref, watch } from 'vue'

import EmptyState from '../components/EmptyState.vue'
import PageHeader from '../components/PageHeader.vue'
import StatCard from '../components/StatCard.vue'
import { PERIODS, getCallLogs, getEndpoints, getOverview, getPerformance, getQuotas } from '../api/analytics.js'
import { formatBytes, formatDateTime, formatMs, formatNumber, formatPercent, statusCodeTone } from '../lib/format.js'
import { toastError } from '../lib/toast.js'

const period = ref('7d')
const loading = ref(true)
const loadingLogs = ref(false)

const overview = ref(null)
const endpoints = ref([])
const performance = ref([])
const quotas = ref([])
const logs = ref({ rows: [], page: 1, pages: 1, total: 0, hasNext: false, hasPrev: false })
const logPage = ref(1)

/** 端点 Top 条形占比（按最大调用量归一） */
const endpointRows = computed(() => {
  const rows = endpoints.value.slice(0, 8)
  if (!rows.length) return []
  const max = Math.max(...rows.map((r) => Number(r.totalCalls) || 0), 1)
  return rows.map((row) => ({
    ...row,
    sharePct: Math.max(2, Math.round(((Number(row.totalCalls) || 0) / max) * 100)),
  }))
})

/** 延迟分位数：跨端点取加权平均的近似展示 */
const latency = computed(() => {
  const rows = performance.value.filter((r) => r.p50 !== null || r.p95 !== null || r.p99 !== null)
  if (!rows.length) return null

  const weighted = (pick) => {
    let totalWeight = 0
    let sum = 0
    rows.forEach((row) => {
      const value = pick(row)
      const weight = Number(row.totalCalls) || 1
      if (value !== null && value !== undefined) {
        sum += value * weight
        totalWeight += weight
      }
    })
    return totalWeight > 0 ? sum / totalWeight : null
  }

  return {
    p50: weighted((r) => r.p50),
    p95: weighted((r) => r.p95),
    p99: weighted((r) => r.p99),
    avg: weighted((r) => r.avgResponseTime),
    rows: rows.length,
  }
})

const totalEndpointCalls = computed(() =>
  endpoints.value.reduce((sum, row) => sum + (Number(row.totalCalls) || 0), 0)
)

async function loadAll() {
  loading.value = true
  const results = await Promise.allSettled([
    getOverview(period.value),
    getEndpoints(period.value),
    getPerformance(period.value),
    getQuotas(),
  ])

  const [ov, ep, pf, qt] = results
  if (ov.status === 'fulfilled') overview.value = ov.value
  if (ep.status === 'fulfilled') endpoints.value = ep.value
  if (pf.status === 'fulfilled') performance.value = pf.value
  if (qt.status === 'fulfilled') quotas.value = qt.value

  if (results.every((r) => r.status === 'rejected')) {
    toastError('统计数据加载失败，请检查后端服务')
  }

  loading.value = false
}

async function loadLogs() {
  loadingLogs.value = true
  try {
    logs.value = await getCallLogs({ period: period.value, page: logPage.value, pageSize: 20 })
  } catch (err) {
    toastError('加载调用日志失败')
    logs.value = { rows: [], page: 1, pages: 1, total: 0, hasNext: false, hasPrev: false }
  } finally {
    loadingLogs.value = false
  }
}

onMounted(() => {
  loadAll()
  loadLogs()
})

watch(period, () => {
  logPage.value = 1
  loadAll()
  loadLogs()
})

function gotoPage(next) {
  if (next < 1) return
  logPage.value = next
  loadLogs()
}

/** 配额条色调 */
function quotaTone(usage) {
  const n = Number(usage) || 0
  if (n >= 95) return 'red'
  if (n >= 80) return 'warn'
  return 'green'
}
</script>

<template>
  <div class="page">
    <PageHeader
      nav="05"
      eyebrow="ANALYTICS"
      title="统计分析"
      desc="调用量、端点分布、响应延迟与配额使用情况。"
    >
      <template #actions>
        <div class="segment" role="tablist" aria-label="统计周期">
          <button
            v-for="item in PERIODS"
            :key="item.value"
            type="button"
            class="segment__item"
            :class="{ 'is-active': period === item.value }"
            role="tab"
            :aria-selected="period === item.value"
            @click="period = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <button type="button" class="btn btn--ghost btn--sm" :disabled="loading" @click="loadAll(); loadLogs()">
          <span v-if="loading" class="spinner"></span>
          <span>{{ loading ? '刷新中' : '刷新' }}</span>
        </button>
      </template>
    </PageHeader>

    <div class="stack stagger">
      <!-- 概览 -->
      <div class="grid grid--4">
        <StatCard label="总调用" :value="overview?.totalCalls ?? null" hint="所选周期内" />
        <StatCard
          label="成功率"
          :value="overview?.successRate ?? null"
          :digits="1"
          unit="%"
          :tone="overview?.successRate === null || overview?.successRate === undefined ? '' : overview.successRate >= 99 ? 'success' : overview.successRate >= 95 ? 'warn' : 'error'"
        />
        <StatCard
          label="平均响应"
          :value="overview?.avgResponseTime ?? null"
          :digits="0"
          unit="ms"
          hint="全端点均值"
        />
        <StatCard label="端点数量" :value="endpoints.length" accent :hint="`共 ${formatNumber(totalEndpointCalls)} 次调用`" />
      </div>

      <!-- 端点 Top + 延迟 -->
      <div class="ana-split">
        <section class="card">
          <div class="card__head">
            <span class="card__title">
              <span class="led led--info" aria-hidden="true"></span>
              端点调用 Top
            </span>
            <span class="tag-mono">BY CALLS</span>
          </div>
          <div class="card__body">
            <div v-if="loading && !endpointRows.length" class="loading-row">
              <span class="spinner"></span>
              <span>LOADING</span>
            </div>

            <div v-else-if="endpointRows.length" class="stack stack--sm">
              <div v-for="row in endpointRows" :key="row.endpoint" class="bar-row">
                <div class="bar-row__main">
                  <div class="bar-row__path truncate" :title="row.endpoint">{{ row.endpoint }}</div>
                  <div class="bar-row__track">
                    <div class="bar-row__fill" :style="{ width: `${row.sharePct}%` }"></div>
                  </div>
                </div>
                <div class="bar-row__num">
                  {{ formatNumber(row.totalCalls) }}
                  <div v-if="row.successRate !== null" class="bar-row__rate" :class="row.successRate >= 99 ? 'text-green' : row.successRate >= 95 ? 'text-warn' : 'text-red'">
                    {{ formatPercent(row.successRate, 1) }}
                  </div>
                </div>
              </div>
            </div>

            <EmptyState v-else icon="∅" title="暂无端点统计" desc="所选周期内没有调用记录。" />
          </div>
        </section>

        <section class="card">
          <div class="card__head">
            <span class="card__title">
              <span class="led led--success" aria-hidden="true"></span>
              响应延迟分位
            </span>
            <span class="tag-mono">LATENCY</span>
          </div>
          <div class="card__body">
            <template v-if="latency">
              <div class="lat">
                <div class="lat__item">
                  <div class="lat__key tag-mono">P50</div>
                  <div class="lat__val num">{{ formatMs(latency.p50) }}</div>
                </div>
                <div class="lat__item">
                  <div class="lat__key tag-mono">P95</div>
                  <div class="lat__val num lat__val--warn">{{ formatMs(latency.p95) }}</div>
                </div>
                <div class="lat__item">
                  <div class="lat__key tag-mono">P99</div>
                  <div class="lat__val num lat__val--red">{{ formatMs(latency.p99) }}</div>
                </div>
                <div class="lat__item">
                  <div class="lat__key tag-mono">AVG</div>
                  <div class="lat__val num">{{ formatMs(latency.avg) }}</div>
                </div>
              </div>
              <div class="field__hint mt-2">基于 {{ latency.rows }} 个端点按调用量加权</div>
            </template>

            <EmptyState v-else icon="∅" title="暂无性能数据" desc="需要至少一次成功的接口调用。" />
          </div>
        </section>
      </div>

      <!-- 传输量 -->
      <div v-if="overview" class="grid grid--2">
        <StatCard
          label="请求流量"
          :value="formatBytes(overview.totalRequestSize)"
          hint="所选周期入站字节"
        />
        <StatCard
          label="响应流量"
          :value="formatBytes(overview.totalResponseSize)"
          hint="所选周期出站字节"
        />
      </div>

      <!-- 配额 -->
      <section v-if="quotas.length" class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--warn" aria-hidden="true"></span>
            配额使用
          </span>
          <span class="tag-mono">QUOTAS</span>
        </div>
        <div class="card__body">
          <div class="stack stack--sm">
            <div v-for="quota in quotas" :key="quota.id" class="quota">
              <div class="quota__head">
                <span class="mono truncate">{{ quota.endpoint }}</span>
                <span class="quota__nums num">
                  {{ formatNumber(quota.quotaUsed) }} / {{ formatNumber(quota.quotaLimit) }}
                  <span class="text-dim">({{ formatPercent(quota.usagePercentage, 1) }})</span>
                </span>
              </div>
              <div class="bar-row__track">
                <div
                  class="bar-row__fill"
                  :class="`bar-row__fill--${quotaTone(quota.usagePercentage)}`"
                  :style="{ width: `${Math.min(100, quota.usagePercentage)}%` }"
                ></div>
              </div>
              <div class="quota__meta">
                <span class="tag-mono">{{ quota.quotaType }}</span>
                <span v-if="quota.resetDate" class="tag-mono">重置 {{ quota.resetDate }}</span>
                <span v-if="quota.isExceeded" class="badge badge--red">已超限</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 调用日志 -->
      <section class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--info" aria-hidden="true"></span>
            调用日志
          </span>
          <span class="tag-mono">共 {{ formatNumber(logs.total) }} 条</span>
        </div>

        <div v-if="loadingLogs" class="loading-row">
          <span class="spinner"></span>
          <span>LOADING</span>
        </div>

        <EmptyState
          v-else-if="!logs.rows.length"
          icon="∅"
          title="暂无调用日志"
          desc="所选周期内没有接口调用记录。"
        />

        <div v-else class="table-wrap table-wrap--plain">
          <table class="table table--compact">
            <thead>
              <tr>
                <th>时间</th>
                <th>方法</th>
                <th>端点</th>
                <th>状态</th>
                <th>延迟</th>
                <th>密钥</th>
                <th>来源 IP</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in logs.rows" :key="log.id ?? `${log.endpoint}-${log.createdAt}`">
                <td class="td-mono td-dim">{{ formatDateTime(log.createdAt) }}</td>
                <td>
                  <span class="method" :class="`method--${String(log.method || 'get').toLowerCase()}`">
                    {{ log.method || 'GET' }}
                  </span>
                </td>
                <td class="td-mono truncate" style="max-width: 230px" :title="log.endpoint">{{ log.endpoint }}</td>
                <td>
                  <span class="badge" :class="log.statusCode ? `badge--${statusCodeTone(log.statusCode)}` : ''">
                    {{ log.statusCode ?? '—' }}
                  </span>
                </td>
                <td class="td-mono">{{ log.responseTime === null ? '—' : formatMs(log.responseTime) }}</td>
                <td class="td-dim truncate" style="max-width: 120px">{{ log.apiKeyName || '—' }}</td>
                <td class="td-mono td-dim">{{ log.requestIp || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="logs.pages > 1" class="pager">
          <span class="pager__info">第 {{ logs.page }} / {{ logs.pages }} 页 · 共 {{ formatNumber(logs.total) }} 条</span>
          <div class="pager__ctrl">
            <button type="button" class="btn btn--ghost btn--sm" :disabled="!logs.hasPrev && logs.page <= 1" @click="gotoPage(logPage - 1)">
              上一页
            </button>
            <span class="pager__page">{{ logs.page }}</span>
            <button type="button" class="btn btn--ghost btn--sm" :disabled="!logs.hasNext && logs.page >= logs.pages" @click="gotoPage(logPage + 1)">
              下一页
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.ana-split {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 1fr);
  gap: 14px;
}

@media (max-width: 1020px) {
  .ana-split {
    grid-template-columns: minmax(0, 1fr);
  }
}

.table-wrap--plain {
  border: none;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
}

.bar-row__rate {
  font-size: 10.5px;
  margin-top: 1px;
}

.bar-row__fill--green {
  background: linear-gradient(90deg, var(--signal-green), rgba(61, 220, 151, 0.5));
}
.bar-row__fill--warn {
  background: linear-gradient(90deg, var(--warn), rgba(255, 194, 75, 0.5));
}
.bar-row__fill--red {
  background: linear-gradient(90deg, var(--signal-red), rgba(255, 92, 92, 0.5));
}

.lat {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 11px;
}

.lat__item {
  padding: 11px 12px;
  background: var(--well);
  border: 1px solid var(--line-soft);
  border-radius: var(--r-md);
}

.lat__key {
  margin-bottom: 4px;
}

.lat__val {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--text);
}

.lat__val--warn {
  color: var(--warn);
}
.lat__val--red {
  color: var(--signal-red);
}

.quota {
  padding: 11px 0;
  border-bottom: 1px solid var(--line-soft);
}

.quota:last-child {
  border-bottom: none;
}

.quota__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 7px;
  font-size: 12.5px;
}

.quota__nums {
  font-size: 12px;
  color: var(--text-dim);
  white-space: nowrap;
}

.quota__meta {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 6px;
}
</style>
