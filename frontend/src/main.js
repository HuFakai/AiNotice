import { createApp } from 'vue'
import { createPinia } from 'pinia'

// 字体本地打包（禁止 CDN）：展示/数字用 IBM Plex Mono，中文正文用 Noto Sans SC
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-mono/600.css'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'
import '@fontsource/noto-sans-sc/700.css'

import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'

import App from './App.vue'
import router from './router/index.js'
import { setNavigator } from './api/client.js'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// 把 router 导航能力注入 HTTP 客户端，供 401 统一跳转使用
setNavigator((target) => router.replace(target))

app.mount('#app')
