/**
 * 路由表（history 模式，配合后端 SPA fallback）
 *
 * 导航编号（侧边栏 mono 序号）与 meta.nav 对应。
 */

import { createRouter, createWebHistory } from 'vue-router'

import AppShell from '../components/AppShell.vue'
import { getToken, isSafeInternalPath } from '../api/client.js'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('../views/RegisterView.vue'),
    meta: { public: true, title: '注册' },
  },
  {
    path: '/',
    component: AppShell,
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { title: '仪表盘', nav: '01' },
      },
      {
        path: 'api-keys',
        name: 'api-keys',
        component: () => import('../views/ApiKeysView.vue'),
        meta: { title: 'API 密钥', nav: '02' },
      },
      {
        path: 'mi-accounts',
        name: 'mi-accounts',
        component: () => import('../views/MiAccountsView.vue'),
        meta: { title: '小米账号', nav: '03' },
      },
      {
        path: 'devices',
        name: 'devices',
        component: () => import('../views/DevicesView.vue'),
        meta: { title: '设备', nav: '04' },
      },
      {
        path: 'analytics',
        name: 'analytics',
        component: () => import('../views/AnalyticsView.vue'),
        meta: { title: '统计分析', nav: '05' },
      },
      {
        path: 'channels',
        name: 'channels',
        component: () => import('../views/ChannelsView.vue'),
        meta: { title: '通知渠道', nav: '06' },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('../views/ProfileView.vue'),
        meta: { title: '个人中心', nav: '07' },
      },
      {
        // 路径说明：后端 FastAPI 把 Swagger UI 挂在 /docs（app/main.py 的 docs_url="/docs"），
        // 该路由注册在 SPA catch-all 之前，因此硬刷新 /docs 会返回 Swagger 而不是本页。
        // 为避免与后端接口文档冲突，前端文档页使用 /api-docs；/docs 作为站内别名重定向。
        path: 'api-docs',
        alias: ['docs'],
        name: 'docs',
        component: () => import('../views/DocsView.vue'),
        meta: { title: '接口文档', nav: '08' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('../views/NotFoundView.vue'),
    meta: { public: true, title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
})

/** 只接受站内 redirect，过滤开放重定向 */
function safeRedirect(value, fallback = '/') {
  return isSafeInternalPath(value) && !value.startsWith('/login') ? value : fallback
}

router.beforeEach((to) => {
  const authed = Boolean(getToken())

  // 已登录访问登录/注册页 → 回首页
  if (authed && (to.name === 'login' || to.name === 'register')) {
    const target = safeRedirect(to.query.redirect, '/')
    return target !== '/' ? target : { path: '/' }
  }

  // 未登录访问受保护页 → 登录页并记录来源
  if (!authed && !to.meta.public) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  return true
})

router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} · 爱通知 AiNotice` : '爱通知 AiNotice'
})

export default router
