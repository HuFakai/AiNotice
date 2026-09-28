<script setup>
/**
 * 接口测试（API Playground）/api-test
 *
 * - 端点清单与接口文档页共用 api/endpoints.js（单一数据源）
 * - 认证：默认当前登录态(JWT)；可切换为从下拉框选择自己的 API 密钥（明文接口直取）
 * - 用独立 fetch（不走 client.js）：4xx/5xx 原样展示，不触发全局 401 跳登录
 * - 请求历史仅保存在内存（最多 20 条）
 */
import { computed, onMounted, ref } from 'vue'

import CopyButton from '../components/CopyButton.vue'
import PageHeader from '../components/PageHeader.vue'
import { API_ENDPOINTS, parseEndpointPath } from '../api/endpoints.js'
import { PERMISSIONS, listApiKeys } from '../api/apiKeys.js'
import { getToken } from '../api/client.js'

const selectedIdx = ref(0)
const endpoint = computed(() => API_ENDPOINTS[selectedIdx.value])

/* 认证 */
const authMode = ref('jwt') // jwt | apikey
const apiKeys = ref([])
const selectedKeyId = ref('')
const keysLoading = ref(false)

async function loadKeys() {
  keysLoading.value = true
  try {
    apiKeys.value = await listApiKeys()
    if (!selectedKeyId.value && apiKeys.value.length) {
      const active = apiKeys.value.find((k) => k.is_active) || apiKeys.value[0]
      selectedKeyId.value = active.id
    }
  } catch {
    apiKeys.value = []
  } finally {
    keysLoading.value = false
  }
}

const selectedKey = computed(() => apiKeys.value.find((k) => String(k.id) === String(selectedKeyId.value)) || null)

onMounted(loadKeys)

/* 参数与请求体 */
const pathParams = ref({})
const queryParams = ref({})
const bodyText = ref('')

/* 响应与历史 */
const sending = ref(false)
const respStatus = ref(null)
const respTime = ref(null)
const respText = ref('')
const respError = ref('')
const history = ref([])

const permLabel = computed(() => {
  const perm = endpoint.value?.perm
  const meta = PERMISSIONS.find((p) => p.key === perm)
  return meta ? `${perm}（${meta.label}）` : perm || '—'
})

function selectEndpoint(idx) {
  selectedIdx.value = idx
  respStatus.value = null
  respTime.value = null
  respText.value = ''
  respError.value = ''
  seedRequest()
}

function seedRequest() {
  const ep = endpoint.value
  const { pathParams: pp, queryKeys } = parseEndpointPath(ep.path)
  pathParams.value = Object.fromEntries(pp.map((k) => [k, '']))
  queryParams.value = Object.fromEntries(queryKeys.map((k) => [k, '']))
  bodyText.value = ep.body ? JSON.stringify(ep.body, null, 2) : ''
}

seedRequest()

const methodTone = computed(() => {
  const m = endpoint.value.method
  return m === 'GET' ? 'badge--info' : m === 'DELETE' ? 'badge--red' : 'badge--accent'
})

function buildUrl() {
  const ep = endpoint.value
  const { cleanPath, pathParams: pp, queryKeys } = parseEndpointPath(ep.path)
  let p = cleanPath
  for (const k of pp) {
    const v = String(pathParams.value[k] ?? '').trim()
    if (!v) return { error: `请填写路径参数 {${k}}` }
    p = p.replace(`{${k}}`, encodeURIComponent(v))
  }
  const qs = queryKeys
    .map((k) => {
      const v = String(queryParams.value[k] ?? '').trim()
      return v ? `${k}=${encodeURIComponent(v)}` : null
    })
    .filter(Boolean)
    .join('&')
  return { url: `/api/v1${p}${qs ? `?${qs}` : ''}` }
}

async function send() {
  if (sending.value) return
  respError.value = ''

  const built = buildUrl()
  if (built.error) {
    respError.value = built.error
    return
  }

  /* 认证头：JWT 或手动粘贴的完整密钥 */
  const headers = { 'Content-Type': 'application/json' }
  if (authMode.value === 'apikey') {
    const key = selectedKey.value?.api_key
    if (!key || !key.startsWith('xai_sk_')) {
      respError.value = '请先选择一个可用的 API 密钥（旧版哈希密钥无明文，请在密钥页重新创建）'
      return
    }
    headers.Authorization = `Bearer ${key}`
  } else {
    const token = getToken()
    if (!token) {
      respError.value = '当前登录态缺失，请重新登录或改用 API 密钥方式'
      return
    }
    headers.Authorization = `Bearer ${token}`
  }

  const method = endpoint.value.method
  const options = { method, headers }
  if (method !== 'GET' && bodyText.value.trim()) {
    try {
      JSON.parse(bodyText.value)
    } catch {
      respError.value = '请求体不是合法的 JSON'
      return
    }
    options.body = bodyText.value
  }

  sending.value = true
  const started = performance.now()
  try {
    const res = await fetch(built.url, options)
    const elapsed = Math.round(performance.now() - started)
    const text = await res.text()
    respStatus.value = res.status
    respTime.value = elapsed
    try {
      respText.value = JSON.stringify(JSON.parse(text), null, 2)
    } catch {
      respText.value = text || '(空响应)'
    }

    history.value.unshift({
      method,
      path: built.url.replace('/api/v1', ''),
      status: res.status,
      ms: elapsed,
      endpointIdx: selectedIdx.value,
      pathParams: { ...pathParams.value },
      queryParams: { ...queryParams.value },
      body: bodyText.value,
      authMode: authMode.value,
      keyId: selectedKeyId.value,
    })
    history.value = history.value.slice(0, 20)
  } catch (err) {
    respError.value = `网络错误: ${err?.message || err}`
    respStatus.value = null
    respTime.value = null
  } finally {
    sending.value = false
  }
}

function restoreHistory(item) {
  selectedIdx.value = item.endpointIdx
  pathParams.value = { ...item.pathParams }
  queryParams.value = { ...item.queryParams }
  bodyText.value = item.body || ''
  authMode.value = item.authMode || 'jwt'
  if (item.keyId) selectedKeyId.value = item.keyId
  respStatus.value = null
  respText.value = ''
}

function statusTone(code) {
  if (code == null) return 'badge--warn'
  if (code < 300) return 'badge--green'
  if (code < 500) return 'badge--warn'
  return 'badge--red'
}
</script>

<template>
  <div>
    <PageHeader
      kicker="09 / API TEST"
      title="接口测试"
      desc="在浏览器里直接调试平台接口：选择端点、填参数、发送并查看真实响应。会真实控制设备的端点请谨慎执行。"
    />

    <div class="test-layout">
      <!-- 左：端点列表 -->
      <aside class="ep-list card">
        <div class="ep-list__head">端点</div>
        <button
          v-for="(ep, i) in API_ENDPOINTS"
          :key="ep.path + ep.method"
          type="button"
          class="ep-item"
          :class="{ 'ep-item--on': i === selectedIdx }"
          @click="selectEndpoint(i)"
        >
          <span class="badge" :class="i === selectedIdx ? 'badge--accent' : 'badge--info'">{{ ep.method }}</span>
          <span class="ep-item__body">
            <span class="ep-item__path">{{ ep.path }}</span>
            <span class="ep-item__desc">{{ ep.desc }}</span>
          </span>
        </button>
      </aside>

      <!-- 右：请求与响应 -->
      <div class="stack test-main">
        <div class="card">
          <div class="req-line">
            <span class="badge" :class="methodTone">{{ endpoint.method }}</span>
            <code class="req-line__path">{{ endpoint.path }}</code>
            <span class="spacer"></span>
            <span class="req-line__perm" :title="`需要权限位: ${endpoint.perm}`">权限: {{ permLabel }}</span>
          </div>

          <div class="field">
            <span class="field__label">认证方式</span>
            <div class="seg" role="tablist">
              <button type="button" class="seg__item" :class="{ 'seg__item--on': authMode === 'jwt' }" :disabled="sending" @click="authMode = 'jwt'">
                当前登录态 (JWT)
              </button>
              <button type="button" class="seg__item" :class="{ 'seg__item--on': authMode === 'apikey' }" :disabled="sending" @click="authMode = 'apikey'">
                API 密钥
              </button>
            </div>
            <div v-if="authMode === 'apikey'" class="mt-2">
              <div v-if="keysLoading" class="field__hint">密钥列表加载中…</div>
              <div v-else-if="!apiKeys.length" class="field__hint">
                还没有 API 密钥：请先到「API 密钥」页创建
              </div>
              <template v-else>
                <select v-model="selectedKeyId" class="select" :disabled="sending">
                  <option v-for="k in apiKeys" :key="k.id" :value="k.id">
                    {{ k.key_name }}（{{ k.is_active ? '有效' : '已禁用' }}）
                  </option>
                </select>
                <div class="field__hint">使用所选密钥的权限位与绑定渠道发起调用</div>
              </template>
            </div>
          </div>

          <div v-if="Object.keys(pathParams).length" class="grid grid--2">
            <div v-for="(v, k) in pathParams" :key="k" class="field">
              <label class="field__label" :for="`pp-${k}`">路径参数 {{ k }}<span class="req">*</span></label>
              <input :id="`pp-${k}`" v-model="pathParams[k]" class="input input--mono" type="text" :disabled="sending" />
            </div>
          </div>

          <div v-if="Object.keys(queryParams).length" class="grid grid--2">
            <div v-for="(v, k) in queryParams" :key="k" class="field">
              <label class="field__label" :for="`qp-${k}`">查询参数 {{ k }}</label>
              <input :id="`qp-${k}`" v-model="queryParams[k]" class="input input--mono" type="text" :disabled="sending" />
            </div>
          </div>

          <div v-if="endpoint.method !== 'GET'" class="field">
            <label class="field__label" for="test-body">请求体 (JSON)</label>
            <textarea id="test-body" v-model="bodyText" class="textarea textarea--mono" rows="8" spellcheck="false" :disabled="sending"></textarea>
          </div>

          <div v-if="respError" class="notice notice--error" role="alert">
            <span class="led led--error" aria-hidden="true"></span>
            <span>{{ respError }}</span>
          </div>

          <div class="row mt-2">
            <button type="button" class="btn btn--primary" :disabled="sending" @click="send">
              <span v-if="sending" class="spinner"></span>
              <span>{{ sending ? '请求中' : '发送请求' }}</span>
            </button>
            <span v-if="respStatus != null" class="badge" :class="statusTone(respStatus)">HTTP {{ respStatus }}</span>
            <span v-if="respTime != null" class="mono-dim">{{ respTime }} ms</span>
          </div>
        </div>

        <div v-if="respText" class="card">
          <div class="resp-head">
            <span class="resp-head__title">响应</span>
            <CopyButton :text="respText" />
          </div>
          <pre class="resp-body">{{ respText }}</pre>
        </div>

        <div v-if="history.length" class="card">
          <div class="resp-head">
            <span class="resp-head__title">调用历史（仅本次会话）</span>
          </div>
          <button
            v-for="(h, i) in history"
            :key="i"
            type="button"
            class="hist-item"
            :title="`回填: ${h.method} ${h.path}`"
            @click="restoreHistory(h)"
          >
            <span class="badge" :class="statusTone(h.status)">{{ h.status }}</span>
            <span class="badge badge--info">{{ h.method }}</span>
            <span class="hist-item__path">{{ h.path }}</span>
            <span class="mono-dim">{{ h.ms }}ms</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.test-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 14px;
  align-items: start;
}

@media (max-width: 920px) {
  .test-layout {
    grid-template-columns: 1fr;
  }
}

.ep-list {
  padding: 8px;
  position: sticky;
  top: 14px;
}

.ep-list__head {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--text-dim);
  padding: 6px 8px 8px;
}

.ep-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 8px;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s ease;
}

.ep-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.ep-item--on {
  background: rgba(255, 105, 0, 0.1);
}

.ep-item__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ep-item__path {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text);
  word-break: break-all;
}

.ep-item__desc {
  font-size: 11.5px;
  color: var(--text-dim);
}

.test-main {
  gap: 14px;
}

.req-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.req-line__path {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text);
  word-break: break-all;
}

.req-line__perm {
  font-size: 12px;
  color: var(--text-dim);
}

.resp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.resp-head__title {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--text-dim);
}

.resp-body {
  margin: 0;
  padding: 12px;
  max-height: 380px;
  overflow: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text);
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--line);
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
}

.hist-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 8px;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s ease;
}

.hist-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.hist-item__path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono-dim {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--text-dim);
}

.textarea--mono {
  font-family: var(--font-mono);
  font-size: 12.5px;
}
</style>
