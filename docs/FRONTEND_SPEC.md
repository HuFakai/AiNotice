# AiNotice 前端重构规格书（FRONTEND_SPEC）

> 本文档是前端重构的唯一施工蓝图。后端 API 前缀统一为 `/api/v1`（除个别历史端点外），开发环境 Vite 代理到后端。

## 1. 技术栈（已定，不要更换）

- **Vue 3（Composition API + `<script setup>`）+ Vite 5 + Vue Router 4（history 模式）+ Pinia**
- 纯 TypeScript 不引入（保持 JavaScript，与后端团队习惯一致），但所有组件用 `defineProps` 等标准写法
- 样式：**手写 CSS 设计系统**（`src/styles/` 下 tokens.css / base.css / components.css），不使用 Tailwind、不使用 Element Plus 等组件库——设计感必须自持
- 字体：`@fontsource` 本地打包（国内可访问性优先，禁止 Google Fonts CDN）：
  - 展示/数字/标签：`@fontsource/ibm-plex-mono`（400/500/600）
  - 中文正文：`@fontsource/noto-sans-sc`（400/500/700）
- 依赖保持最少：vue / vue-router / pinia / @vitejs/plugin-vue / vite / 两个 fontsource 包。HTTP 用封装的 `fetch`，不引入 axios
- Node 24 已安装。构建产物输出到 `frontend/dist`，由 FastAPI 静态托管 + SPA fallback

## 2. 美学方向（必须遵守，来自 frontend-design skill）

**方向：「信号控制台」（Signal Console）— 深色工业风设备控制台美学**

这是一个"小爱音箱消息推送 API 平台"的管理控制台。用户是开发者/设备管理者。视觉要传达：可靠、精密、设备在线的"信号感"。

- **色彩（CSS variables，在 tokens.css 中定义）**：
  - 背景基调：`--bg: #0B0E14`（墨蓝黑）、面板 `--panel: #12161F`、面板浮起 `--panel-2: #1A2030`
  - 主强调：**小米橙 `--accent: #FF6900`**（CTA、活跃态、logo），hover `#FF8A3D`
  - 信号色：在线/成功 `--signal-green: #3DDC97`、告警 `--signal-red: #FF5C5C`、信息 `--info: #4CC9F0`、等待 `--warn: #FFC24B`
  - 文本：`--text: #E8ECF4`、次级 `--text-dim: #8A94A8`、边框 hairline `--line: #232A38`
  - 禁止：紫色渐变、白底紫按钮等"AI 味"配色
- **质感与氛围**：
  - 全局极淡的点阵网格背景（CSS radial-gradient 生成，opacity ≤ 0.04）
  - 状态一律用 **LED 圆点**（带同色 box-shadow 光晕）表达在线/离线/成功/失败
  - 卡片：1px hairline 边框 + 极浅顶部高光内阴影，圆角 10px；hover 轻微上浮 + 边框提亮
  - 页头区域可加一条 2px 的 accent 渐变细线（橙→透明）作为"信号线"签名元素
- **字体排印**：
  - 数字/指标/ID/时间戳/API Key/端点路径一律 IBM Plex Mono
  - 标题用 Noto Sans SC 700，字距略收紧；正文 400
  - 侧边栏导航项带 mono 编号（01/02/03…）作为工业感细节
- **动效（CSS 优先）**：
  - 页面进入：内容块 `fadeUp` 交错入场（animation-delay 递增 40ms）
  - 仪表盘数字用 `@property` + counter 或 JS ticker 做 600ms 滚动
  - LED 呼吸、按钮 hover 位移 1px、focus-visible 橙色描边
  - `prefers-reduced-motion: reduce` 时全部关闭
- **布局**：
  - 桌面：左侧 232px 固定侧边栏 + 右侧内容区（max-width 1280 居中）
  - ≤920px：侧边栏收起为顶部条 + 抽屉；所有表格可横向滚动
  - 登录/注册：无侧边栏，居中卡片 + 点阵背景 + 底部平台签名

## 3. 工程结构

```
frontend/
  package.json  vite.config.js  index.html
  src/
    main.js  App.vue  router/index.js
    styles/        tokens.css base.css components.css
    api/           client.js（fetch 封装）auth.js apiKeys.js miAccounts.js
                   devices.js analytics.js channels.js notify.js
    stores/        auth.js（Pinia：token、user、login/logout/fetchMe）
    components/    AppShell.vue（侧边栏+顶栏外壳） StatusLed.vue StatCard.vue
                   Modal.vue Toast.vue CopyButton.vue EmptyState.vue
                   QrLoginModal.vue ConfirmDialog.vue PageHeader.vue
    views/         LoginView.vue RegisterView.vue DashboardView.vue
                   ApiKeysView.vue MiAccountsView.vue DevicesView.vue
                   AnalyticsView.vue ChannelsView.vue ProfileView.vue
                   DocsView.vue NotFoundView.vue
```

## 4. 认证与请求层约定（src/api/client.js）

- 登录后 token 存 `localStorage.auth_token`（键名必须是 `auth_token`）
- `request(path, {method, body, auth})`：自动带 `Authorization: Bearer <token>`；JSON 解析后**统一取 `detail` 或 `message` 作为错误文案**
- **401 处理：清除 token → 跳转 `/login?redirect=当前路径`，带防抖（同一时刻只跳一次）**；`redirect` 只允许站内路径（以 `/` 开头且不含 `//`），防开放重定向
- 所有列表接口返回 `{数据}` 或数组；后端 5xx 显示统一 toast"服务暂时不可用"
- **任何 innerHTML 都不允许拼接用户/接口数据**；渲染一律用模板插值（Vue 自动转义）。复制功能用 `navigator.clipboard`

## 5. 页面与 API 契约

### 登录 `/login`
- POST `/api/v1/auth/login` body `{username_or_email, password}` → `{access_token, token_type, user:{...}}`
- 登录限流：失败 5 次锁 15 分钟——错误文案原样展示（后端返回"尝试过于频繁"等）
- 已登录访问 /login 自动跳 /

### 注册 `/register`
- POST `/api/v1/auth/register` `{username, email, password, display_name?}` → `SuccessResponse`
- 可用性检查：POST `/auth/check-username` `{username}`、POST `/auth/check-email` `{email}` → `{available, message}`（输入停顿 500ms 防抖后检查）
- 注册开关被服务端关闭时后端返回 400，展示 detail

### 应用外壳 AppShell
- 侧边栏：logo（橙色信号点 + "爱通知 AiNotice" mono 副标）、导航（编号 01-08）：仪表盘 `/`、API密钥 `/api-keys`、小米账号 `/mi-accounts`、设备 `/devices`、统计分析 `/analytics`、通知渠道 `/channels`、个人中心 `/profile`、接口文档 `/docs`
- 顶部条：当前用户名 + 登出按钮（POST `/api/v1/auth/logout` 后清 token 跳 /login）
- 路由守卫：无 token 全部重定向 /login（登录注册除外）

### 仪表盘 `/`
- GET `/api/v1/analytics/overview`（总调用、成功率、活跃密钥、今日调用——以实际返回字段为准，先 console 打印一次真实结构再对齐字段）
- GET `/api/v1/analytics/real-time`（QPS/实时状态）
- GET `/api/v1/user/stats`、GET `/api/v1/mi-accounts/stats/summary`
- 布局：顶部 4 张 StatCard（mono 大数字 + LED），中部近 7 日调用量（用纯 CSS/SVG 柱状图，自绘，不引图表库），底部最近调用列表（GET `/api/v1/analytics/call-logs?page_size=8`）

### API 密钥 `/api-keys`
- GET `/api/v1/api-keys` → 列表，**`api_key` 字段是掩码**（如 `xai_sk_****abcd`），列表页只显示掩码
- POST `/api/v1/api-keys` `{key_name, permissions, expires_in_days?, usage_limit?}` → **响应里的 api_key 是完整明文，仅此一次**：弹出"密钥已创建"模态，强制展示完整 key + 复制按钮 + "我已保存"确认后才关闭
- PUT `/api/v1/api-keys/{id}`（key_name/permissions/is_active/usage_limit）、DELETE（ConfirmDialog 确认）
- 权限编辑用开关组：speak / get_devices / manage_devices / stop_speak / set_volume / get_status（中文标签见 docs 页）

### 小米账号 `/mi-accounts`（含扫码登录）
- GET `/api/v1/mi-accounts` → 列表（sync_status：pending/success/failed LED + device_count）
- **扫码登录（重点新功能）**：
  1. 「扫码登录」按钮打开 QrLoginModal
  2. POST `/api/v1/mi-accounts/qr/create` body `{name?}` → `{session_id, qr_image_url, login_url, expires_in}`
  3. `<img :src="qr_image_url">` 直接显示（后端代理 PNG）；下方小字"请用小米账号 App 扫码"
  4. 每 2.5s GET `/api/v1/mi-accounts/qr/{session_id}/status` → `{status: waiting|confirmed|expired|error, message, account_id?}`
  5. confirmed → 成功态（LED 变绿 + 打勾动画），1.5s 后关闭并刷新列表；expired/error → 显示重试按钮
  6. 组件卸载时停止轮询
- 密码添加：POST `/api/v1/mi-accounts/simplified` `{mi_username, mi_password}`
- 每行操作：同步 POST `/{id}/sync`、测试 POST `/{id}/test`、删除 DELETE `/{id}`
- GET `/api/v1/mi-accounts/{id}` 详情（含设备）

### 设备 `/devices`
- GET `/api/v1/devices` → `{devices:[...]}`（名称/型号/在线 LED/音量/所属账号）
- 音量：行内滑杆，POST `/api/v1/devices/{device_id}/volume` `{volume}`（0-100，**0 是合法值不要用 || 兜底**）
- 播放测试：选设备输入文本 POST `/api/v1/speak/{device_id}` `{content}`（ SpeakRequest 结构以 src/api/devices.js 实测为准）；停止按钮 POST `/api/v1/speak/stop` `{device_id}`（query 或 body，实测对齐）
- 刷新：POST `/api/v1/mi-accounts/refresh-all-devices`

### 统计分析 `/analytics`
- 周期选择 24h/7d/30d（mono 分段控件）
- GET `/analytics/overview`、`/analytics/endpoints?period=`、`/analytics/performance?period=`、`/analytics/quotas`、`/analytics/call-logs?period=&page=`
- 端点 Top 表格（mono 路径 + 请求条形占比）、延迟 P50/P95/P99 卡片、调用日志分页表

### 通知渠道 `/channels`
- GET/POST/PUT/DELETE `/api/v1/channels`
- channel_type：`email / dingtalk / feishu / wechat / webhook / speak`（分类型动态表单）：
  - email: smtp_host, smtp_port, smtp_user, smtp_password(密码框), smtp_ssl(bool), from_name, to_address
  - dingtalk/feishu: webhook_url, secret(钉钉/飞书可选)
  - wechat: webhook_url(企业微信机器人 key)
  - webhook: url, method, headers(JSON 文本域)
  - speak: 无配置（用绑定的音箱念出来）
- **编辑时**：密码/secret 类字段一律留空显示"已配置，留空保持不变"（后端对空值/`******` 自动保留旧值）；不要把接口返回的掩码回填提交
- 测试按钮：POST `/api/v1/channels/{id}/test` → `{success, message, log_id}` **真实结果**，失败红色 toast 展示 message
- 每渠道卡片显示最后测试状态（如接口返回）

### 个人中心 `/profile`
- GET/PUT `/api/v1/user/profile`、POST `/api/v1/user/change-password` `{old_password, new_password}`
- GET `/api/v1/user/activities`、`/api/v1/user/stats`、`/api/v1/user/login-history`
- 改密成功后提示"其他设备已强制下线"（后端会递增 token_version 使旧 token 失效）

### 接口文档 `/docs`
- 静态排版页：平台简介、快速开始（创建密钥 → 调用示例 curl）、各端点表格、权限位说明、错误码。mono 代码块 + 复制按钮。内容参考旧 `frontend/pages/docs.html` 的文案改写

### 404 `/_:pathMatch(.*)*` → NotFoundView

## 6. 部署接线（后端已/将处理，前端无需关心）

- `npm run build` 产出 `frontend/dist`
- FastAPI 托管 dist + SPA fallback（`/login` `/api-keys` 等路径直接返回 index.html）
- 开发时 `npm run dev`，vite.config.js 中 `server.proxy`：`'/api' → http://127.0.0.1:9000`（后端端口读 .env 的 API_PORT，当前为 9000）

## 7. 验收标准

- `npm run build` 零报错；`npm run dev` 可跑通登录→仪表盘全流程（对接本地后端）
- 无任何 `innerHTML` 拼接数据；XSS 面 = 0
- 无硬编码 `localhost:8000`；一切请求走 client.js
- 移动端 920px 断点可用；`prefers-reduced-motion` 生效
- 视觉符合第 2 节设计系统：小米橙 + 墨蓝黑 + LED + IBM Plex Mono 数字
