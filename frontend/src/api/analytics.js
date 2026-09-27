/**
 * 统计分析接口
 *
 * 实测响应结构（app/schemas/analytics.py）：
 *   GET /analytics/overview  → {success, data: OverviewStats, time_series: [...], message}
 *   GET /analytics/endpoints → {success, data: [EndpointStats], time_series: [...]}
 *   GET /analytics/performance → {success, data: [PerformanceStats], time_series: [...]}
 *   GET /analytics/quotas    → {success, data: [QuotaUsage]}
 *   GET /analytics/real-time → {success, data: {current_qps, active_users, recent_calls, system_health, alerts}}
 *   GET /analytics/call-logs → {success, data: [ApiCallLog], pagination: {...}}
 */

import { get, toData, toList, numOr } from './client.js'

/** 支持的统计周期 */
export const PERIODS = [
  { value: '24h', label: '24H' },
  { value: '7d', label: '7D' },
  { value: '30d', label: '30D' },
]

/** 概览：返回 {stats, timeSeries} —— 全部字段做了容错，字段缺失也不会白屏 */
export async function getOverview(period = '7d') {
  const payload = await get('/analytics/overview', { period }, { silent: true })
  const stats = toData(payload, {}) || {}
  const timeSeries = Array.isArray(payload?.time_series) ? payload.time_series : []

  return {
    totalCalls: numOr(stats.total_calls, 0),
    successRate: Number.isFinite(Number(stats.success_rate)) ? Number(stats.success_rate) : null,
    avgResponseTime: Number.isFinite(Number(stats.avg_response_time)) ? Number(stats.avg_response_time) : null,
    totalRequestSize: numOr(stats.total_request_size, 0),
    totalResponseSize: numOr(stats.total_response_size, 0),
    topEndpoints: Array.isArray(stats.top_endpoints) ? stats.top_endpoints : [],
    errorDistribution: Array.isArray(stats.error_distribution) ? stats.error_distribution : [],
    periodComparison: stats.period_comparison || null,
    timeSeries: timeSeries.map((point) => ({
      timestamp: point?.timestamp ?? '',
      calls: numOr(point?.calls, 0),
      successCalls: numOr(point?.success_calls, 0),
      errorCalls: numOr(point?.error_calls, 0),
      avgResponseTime: Number.isFinite(Number(point?.avg_response_time)) ? Number(point.avg_response_time) : null,
    })),
  }
}

/** 端点统计 */
export async function getEndpoints(period = '7d') {
  const payload = await get('/analytics/endpoints', { period }, { silent: true })
  const rows = toList(payload, 'data')
  return rows.map((row) => ({
    endpoint: row?.endpoint || '-',
    totalCalls: numOr(row?.total_calls, 0),
    successCalls: numOr(row?.success_calls, 0),
    errorCalls: numOr(row?.error_calls, 0),
    successRate: Number.isFinite(Number(row?.success_rate)) ? Number(row.success_rate) : null,
    avgResponseTime: Number.isFinite(Number(row?.avg_response_time)) ? Number(row.avg_response_time) : null,
  }))
}

/** 性能统计（P50/P95/P99） */
export async function getPerformance(period = '7d') {
  const payload = await get('/analytics/performance', { period }, { silent: true })
  const rows = toList(payload, 'data')
  return rows.map((row) => ({
    endpoint: row?.endpoint || '-',
    avgResponseTime: Number.isFinite(Number(row?.avg_response_time)) ? Number(row.avg_response_time) : null,
    p50: Number.isFinite(Number(row?.p50_response_time)) ? Number(row.p50_response_time) : null,
    p95: Number.isFinite(Number(row?.p95_response_time)) ? Number(row.p95_response_time) : null,
    p99: Number.isFinite(Number(row?.p99_response_time)) ? Number(row.p99_response_time) : null,
    min: Number.isFinite(Number(row?.min_response_time)) ? Number(row.min_response_time) : null,
    max: Number.isFinite(Number(row?.max_response_time)) ? Number(row.max_response_time) : null,
    totalCalls: numOr(row?.total_calls, 0),
    qps: Number.isFinite(Number(row?.qps)) ? Number(row.qps) : null,
  }))
}

/** 配额使用情况 */
export async function getQuotas() {
  const payload = await get('/analytics/quotas', null, { silent: true })
  const rows = toList(payload, 'data')
  return rows.map((row) => ({
    id: row?.id,
    endpoint: row?.endpoint || '-',
    quotaType: row?.quota_type || '',
    quotaLimit: numOr(row?.quota_limit, 0),
    quotaUsed: numOr(row?.quota_used, 0),
    quotaRemaining: numOr(row?.quota_remaining, 0),
    usagePercentage: numOr(row?.usage_percentage, 0),
    isExceeded: Boolean(row?.is_exceeded),
    resetDate: row?.reset_date || null,
  }))
}

/** 实时状态 */
export async function getRealTime() {
  const payload = await get('/analytics/real-time', null, { silent: true })
  const data = toData(payload, {}) || {}
  return {
    currentQps: numOr(data.current_qps, 0),
    activeUsers: numOr(data.active_users, 0),
    recentCalls: Array.isArray(data.recent_calls) ? data.recent_calls : [],
    systemHealth: data.system_health && typeof data.system_health === 'object' ? data.system_health : {},
    alerts: Array.isArray(data.alerts) ? data.alerts : [],
  }
}

/** 调用记录分页 */
export async function getCallLogs({ period, page = 1, pageSize = 20, endpoint, statusCode } = {}) {
  const payload = await get(
    '/analytics/call-logs',
    {
      period,
      page,
      limit: pageSize,
      endpoint,
      status_code: statusCode,
    },
    { silent: true }
  )

  const rows = toList(payload, 'data')
  const pagination = payload?.pagination && typeof payload.pagination === 'object' ? payload.pagination : {}

  return {
    rows: rows.map(normalizeCallLog),
    page: numOr(pagination.page, page),
    pageSize: numOr(pagination.limit, pageSize),
    total: numOr(pagination.total, rows.length),
    pages: numOr(pagination.pages, 1),
    hasNext: Boolean(pagination.has_next),
    hasPrev: Boolean(pagination.has_prev),
  }
}

/** 调用记录字段归一化（后端字段名可能微调，这里全部可选） */
export function normalizeCallLog(row) {
  if (!row || typeof row !== 'object') return {}
  return {
    id: row.id,
    endpoint: row.endpoint || '-',
    method: row.method || '',
    statusCode: Number.isFinite(Number(row.status_code)) ? Number(row.status_code) : null,
    responseTime: Number.isFinite(Number(row.response_time_ms)) ? Number(row.response_time_ms) : null,
    apiKeyName: row.api_key_name || '',
    deviceName: row.device_name || '',
    deviceId: row.device_id || '',
    speakText: row.speak_text || '',
    requestIp: row.request_ip || '',
    errorMessage: row.error_message || '',
    createdAt: row.created_at || null,
    isSuccess: row.is_success ?? (Number(row.status_code) >= 200 && Number(row.status_code) < 300),
    raw: row,
  }
}
