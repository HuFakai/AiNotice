<script setup>
/**
 * 接口文档 /docs
 * 静态排版页：平台简介、快速开始、端点表格、权限位说明、错误码。
 * 所有代码块用模板插值渲染 + CopyButton 复制，不使用 innerHTML。
 */
import { computed } from 'vue'

import CopyButton from '../components/CopyButton.vue'
import PageHeader from '../components/PageHeader.vue'
import { PERMISSIONS } from '../api/apiKeys.js'

/** 基础地址用当前站点推导，避免硬编码公网域名 */
const baseUrl = computed(() => {
  if (typeof window === 'undefined') return '/api/v1'
  return `${window.location.origin}/api/v1`
})

const endpoints = [
  { method: 'POST', path: '/speak', desc: '播放文字（支持单设备与多设备数组）', perm: 'speak' },
  { method: 'GET', path: '/speak/devices', desc: '获取当前账号下的设备列表', perm: 'get_devices' },
  { method: 'GET', path: '/speak/{device_id}', desc: '获取单个设备详情与状态', perm: 'get_status' },
  { method: 'POST', path: '/speak/{device_id}', desc: '向指定设备下发播报', perm: 'speak' },
  { method: 'POST', path: '/speak/{device_id}/volume?volume=0-100', desc: '设置设备音量', perm: 'set_volume' },
  { method: 'POST', path: '/speak/stop?device_id=', desc: '停止指定设备的播报', perm: 'stop_speak' },
  { method: 'GET', path: '/speak/status/{task_id}', desc: '查询播报任务状态', perm: 'get_status' },
  { method: 'POST', path: '/speak/devices/scan', desc: '强制刷新设备缓存', perm: 'manage_devices' },
  { method: 'POST', path: '/notify/send', desc: '统一推送：显式指定渠道，或不带渠道参数时发到密钥绑定的全部启用渠道', perm: 'send_notify' },
]

const errorCodes = [
  { code: '200', text: '成功', tone: 'green' },
  { code: '400', text: '请求参数有误，检查 body / query', tone: 'warn' },
  { code: '401', text: '未认证或令牌失效，检查 Authorization 头', tone: 'warn' },
  { code: '403', text: '密钥缺少该端点所需的权限位', tone: 'red' },
  { code: '404', text: '资源不存在（设备、任务或端点）', tone: 'warn' },
  { code: '429', text: '触发限流，稍后重试', tone: 'warn' },
  { code: '500', text: '服务端异常，可查看 error_message 字段', tone: 'red' },
]

const curlSpeak = computed(
  () => `curl -s -X POST "${baseUrl.value}/speak" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
    "text": "你好，这是一条测试播报",
    "device_id": "445777160",
    "volume": 60
  }'`
)

const curlMulti = computed(
  () => `curl -s -X POST "${baseUrl.value}/speak" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
    "text": "紧急通知：会议将在 5 分钟后开始",
    "device_id": ["445777160", "445777161"],
    "volume": 80
  }'`
)

const curlDevices = computed(
  () => `curl -s -X GET "${baseUrl.value}/speak/devices" \\
  -H "Authorization: Bearer $XAI_API_KEY"`
)

const curlVolume = computed(
  () => `# 音量 0-100 均为合法值，0 表示静音
curl -s -X POST "${baseUrl.value}/speak/445777160/volume?volume=35" \\
  -H "Authorization: Bearer $XAI_API_KEY"`
)

const pythonSnippet = computed(
  () => `import os, requests

BASE = os.environ["XAI_API_URL"]        # ${baseUrl.value}
KEY  = os.environ["XAI_API_KEY"]        # xai_sk_...

resp = requests.post(
    f"{BASE}/speak",
    headers={"Authorization": f"Bearer {KEY}"},
    json={"text": "来自 Python 的播报", "device_id": "445777160"},
    timeout=10,
)
resp.raise_for_status()
print(resp.json())`
)

const nodeSnippet = computed(
  () => `const BASE = process.env.XAI_API_URL;   // ${baseUrl.value}
const KEY  = process.env.XAI_API_KEY;

const res = await fetch(\`\${BASE}/speak\`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: \`Bearer \${KEY}\`,
  },
  body: JSON.stringify({ text: '来自 Node 的播报', device_id: '445777160' }),
});

if (!res.ok) throw new Error(\`HTTP \${res.status}\`);
console.log(await res.json());`
)

const envSnippet = computed(
  () => `# macOS / Linux
export XAI_API_URL="${baseUrl.value}"
export XAI_API_KEY="xai_sk_xxxxxxxxxxxxxxxxxxxx"

# Windows PowerShell
$env:XAI_API_URL="${baseUrl.value}"
$env:XAI_API_KEY="xai_sk_xxxxxxxxxxxxxxxxxxxx"`
)

function methodClass(method) {
  return `method--${String(method).toLowerCase()}`
}
</script>

<template>
  <div class="page">
    <PageHeader
      nav="08"
      eyebrow="API DOCS"
      title="接口文档"
      desc="使用 API 密钥在服务端调用平台能力：播报、设备管理、音量调节与统一推送。"
    />

    <div class="stack stagger docs">
      <!-- 基础信息 -->
      <section class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--info" aria-hidden="true"></span>
            基础信息
          </span>
          <CopyButton :text="baseUrl" label="复制地址" subject="接口地址" />
        </div>
        <div class="card__body">
          <div class="dl">
            <div class="dl__item">
              <div class="dl__key">Base URL</div>
              <div class="dl__val mono break-all">{{ baseUrl }}</div>
            </div>
            <div class="dl__item">
              <div class="dl__key">认证方式</div>
              <div class="dl__val mono">Authorization: Bearer xai_sk_...</div>
            </div>
            <div class="dl__item">
              <div class="dl__key">请求格式</div>
              <div class="dl__val mono">application/json</div>
            </div>
            <div class="dl__item">
              <div class="dl__key">设备 ID</div>
              <div class="dl__val">取自「设备」页的设备 ID 列</div>
            </div>
          </div>

          <div class="notice notice--warn mt-3">
            <span class="led led--warn" aria-hidden="true"></span>
            <span>
              请仅在服务端或受信任环境中使用 API 密钥。密钥一旦写入前端代码或公开仓库即可被滥用，
              建议通过环境变量注入并定期轮换。
            </span>
          </div>
        </div>
      </section>

      <!-- 快速开始 -->
      <section class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--active" aria-hidden="true"></span>
            快速开始
          </span>
          <span class="tag-mono">3 STEPS</span>
        </div>
        <div class="card__body">
          <ol class="steps">
            <li class="step">
              <span class="step__num mono">01</span>
              <div class="step__body">
                <div class="step__title">创建 API 密钥</div>
                <p class="step__desc">
                  在 <RouterLink to="/api-keys">API 密钥</RouterLink> 页创建密钥，按需勾选权限位。
                  完整密钥仅展示一次，请立即保存。
                </p>
              </div>
            </li>
            <li class="step">
              <span class="step__num mono">02</span>
              <div class="step__body">
                <div class="step__title">配置环境变量</div>
                <p class="step__desc">把地址与密钥写入运行环境，避免硬编码在代码里。</p>
                <div class="code">
                  <CopyButton :text="envSnippet" label="复制" subject="环境变量" />
                  <pre><code>{{ envSnippet }}</code></pre>
                </div>
              </div>
            </li>
            <li class="step">
              <span class="step__num mono">03</span>
              <div class="step__body">
                <div class="step__title">发起第一次调用</div>
                <p class="step__desc">先拉设备列表拿到 device_id，再下发播报。</p>
                <div class="code">
                  <CopyButton :text="curlDevices" label="复制" subject="示例" />
                  <pre><code>{{ curlDevices }}</code></pre>
                </div>
              </div>
            </li>
          </ol>
        </div>
      </section>

      <!-- 播报示例 -->
      <section class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--success" aria-hidden="true"></span>
            播报调用示例
          </span>
          <span class="tag-mono">POST /speak</span>
        </div>
        <div class="card__body">
          <div class="grid grid--2">
            <div class="code">
              <div class="code__head">
                <span class="tag-mono">单设备</span>
                <CopyButton :text="curlSpeak" label="复制" subject="curl 示例" />
              </div>
              <pre><code>{{ curlSpeak }}</code></pre>
            </div>

            <div class="code">
              <div class="code__head">
                <span class="tag-mono">多设备并行</span>
                <CopyButton :text="curlMulti" label="复制" subject="curl 示例" />
              </div>
              <pre><code>{{ curlMulti }}</code></pre>
            </div>

            <div class="code">
              <div class="code__head">
                <span class="tag-mono">Python</span>
                <CopyButton :text="pythonSnippet" label="复制" subject="Python 示例" />
              </div>
              <pre><code>{{ pythonSnippet }}</code></pre>
            </div>

            <div class="code">
              <div class="code__head">
                <span class="tag-mono">Node.js</span>
                <CopyButton :text="nodeSnippet" label="复制" subject="Node 示例" />
              </div>
              <pre><code>{{ nodeSnippet }}</code></pre>
            </div>
          </div>

          <div class="hr"></div>

          <div class="code">
            <div class="code__head">
              <span class="tag-mono">音量控制</span>
              <CopyButton :text="curlVolume" label="复制" subject="音量示例" />
            </div>
            <pre><code>{{ curlVolume }}</code></pre>
          </div>

          <div class="notice notice--info mt-3">
            <span class="led led--info" aria-hidden="true"></span>
            <span>
              请求体字段：<code class="mono">text</code>（1-500 字，必填）、
              <code class="mono">device_id</code>（字符串或数组）、
              <code class="mono">volume</code> / <code class="mono">endvolume</code>（0-100）、
              <code class="mono">speed</code>（0.5-2.0）、
              <code class="mono">voice_type</code>（male / female / child）。
            </span>
          </div>
        </div>
      </section>

      <!-- 端点表 -->
      <section class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--info" aria-hidden="true"></span>
            端点一览
          </span>
          <span class="tag-mono">{{ endpoints.length }} ENDPOINTS</span>
        </div>

        <div class="table-wrap table-wrap--plain">
          <table class="table table--compact">
            <thead>
              <tr>
                <th>方法</th>
                <th>路径</th>
                <th>说明</th>
                <th>所需权限</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ep in endpoints" :key="`${ep.method}-${ep.path}`">
                <td><span class="method" :class="methodClass(ep.method)">{{ ep.method }}</span></td>
                <td class="td-mono">{{ ep.path }}</td>
                <td class="td-dim">{{ ep.desc }}</td>
                <td><span class="badge badge--accent">{{ ep.perm }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 权限位 -->
      <section class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--warn" aria-hidden="true"></span>
            权限位说明
          </span>
          <span class="tag-mono">{{ PERMISSIONS.length }} SCOPES</span>
        </div>
        <div class="card__body">
          <div class="perm-grid">
            <div v-for="perm in PERMISSIONS" :key="perm.key" class="perm-item">
              <span class="perm-item__text">
                <span class="perm-item__name">{{ perm.key }}</span>
                <span class="perm-item__desc">{{ perm.label }} · {{ perm.desc }}</span>
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- 错误码 -->
      <section class="card">
        <div class="card__head">
          <span class="card__title">
            <span class="led led--error" aria-hidden="true"></span>
            错误码
          </span>
        </div>

        <div class="table-wrap table-wrap--plain">
          <table class="table table--compact">
            <thead>
              <tr>
                <th style="width: 90px">状态码</th>
                <th>含义与排查建议</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in errorCodes" :key="item.code">
                <td><span class="badge" :class="`badge--${item.tone}`">{{ item.code }}</span></td>
                <td class="td-dim">{{ item.text }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card__body">
          <div class="code">
            <div class="code__head">
              <span class="tag-mono">错误响应示例</span>
            </div>
            <pre><code>{{ '{' }}
  "success": false,
  "message": "密钥缺少该端点所需的权限位: speak",
  "detail": null
{{ '}' }}</code></pre>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.code {
  position: relative;
  background: var(--well);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  overflow: hidden;
}

.code__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 11px;
  border-bottom: 1px solid var(--line-soft);
  background: rgba(255, 255, 255, 0.014);
}

.code pre {
  margin: 0;
  padding: 12px 13px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-dim);
  tab-size: 2;
}

.code code {
  font-family: var(--font-mono);
  white-space: pre;
}

.steps {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.step {
  display: flex;
  gap: 14px;
}

.step__num {
  flex: none;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  background: var(--accent-dim);
  border: 1px solid var(--accent-line);
  border-radius: var(--r-md);
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-hover);
}

.step__body {
  flex: 1;
  min-width: 0;
}

.step__title {
  font-size: 13.5px;
  font-weight: 500;
  margin-bottom: 3px;
}

.step__desc {
  font-size: 12.5px;
  color: var(--text-mute);
  margin-bottom: 9px;
  line-height: 1.65;
}

.table-wrap--plain {
  border: none;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
}

@media (max-width: 920px) {
  .code pre {
    font-size: 11px;
  }
}
</style>
