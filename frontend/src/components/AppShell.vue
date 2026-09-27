<script setup>
/**
 * 应用外壳：左侧 232px 侧边栏 + 右侧内容区
 * - 导航项带 mono 编号（01-08）作为工业感细节
 * - ≤920px 收起为顶部条 + 抽屉
 * - 顶栏显示当前用户名 + 登出
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth.js'
import { toastError, toastSuccess } from '../lib/toast.js'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const drawerOpen = ref(false)
const loggingOut = ref(false)

const NAV = [
  { to: '/', num: '01', label: '仪表盘', hint: '总览与实时状态' },
  { to: '/api-keys', num: '02', label: 'API 密钥', hint: '密钥与权限位' },
  { to: '/mi-accounts', num: '03', label: '小米账号', hint: '绑定与扫码' },
  { to: '/devices', num: '04', label: '设备', hint: '音箱与音量' },
  { to: '/analytics', num: '05', label: '统计分析', hint: '调用与性能' },
  { to: '/channels', num: '06', label: '通知渠道', hint: '推送目标' },
  { to: '/profile', num: '07', label: '个人中心', hint: '资料与安全' },
  { to: '/api-docs', num: '08', label: '接口文档', hint: '端点与示例' },
]

const currentTitle = computed(() => route.meta?.title || '控制台')
const currentNav = computed(() => route.meta?.nav || '00')

function isActive(to) {
  if (to === '/') return route.path === '/'
  return route.path === to || route.path.startsWith(`${to}/`)
}

// 路由变化时收起抽屉
watch(() => route.fullPath, () => {
  drawerOpen.value = false
})

function onKeydown(e) {
  if (e.key === 'Escape') drawerOpen.value = false
}

watch(drawerOpen, (open) => {
  if (typeof document === 'undefined') return
  if (open) document.addEventListener('keydown', onKeydown)
  else document.removeEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  if (typeof document !== 'undefined') document.removeEventListener('keydown', onKeydown)
})

async function onLogout() {
  loggingOut.value = true
  try {
    await auth.logout()
    toastSuccess('已安全退出')
    router.replace('/login')
  } catch (err) {
    toastError('退出时发生异常，已清理本地登录状态')
    router.replace('/login')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <div class="shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>

    <!-- ============ 侧边栏 ============ -->
    <aside class="sidebar" :class="{ 'sidebar--open': drawerOpen }">
      <div class="sidebar__brand">
        <span class="brand__dot" aria-hidden="true">
          <i></i>
        </span>
        <div class="brand__text">
          <div class="brand__name">爱通知</div>
          <div class="brand__sub">AINOTICE · API</div>
        </div>
      </div>

      <nav class="sidebar__nav" aria-label="主导航">
        <RouterLink
          v-for="item in NAV"
          :key="item.to"
          :to="item.to"
          class="navitem"
          :class="{ 'navitem--active': isActive(item.to) }"
        >
          <span class="navitem__num">{{ item.num }}</span>
          <span class="navitem__body">
            <span class="navitem__label">{{ item.label }}</span>
            <span class="navitem__hint">{{ item.hint }}</span>
          </span>
        </RouterLink>
      </nav>

      <div class="sidebar__foot">
        <div class="sidebar__status">
          <span class="led led--success" aria-hidden="true"></span>
          <span class="tag-mono">SESSION ACTIVE</span>
        </div>
      </div>
    </aside>

    <!-- 移动端遮罩 -->
    <Transition name="fade">
      <div v-if="drawerOpen" class="scrim" @click="drawerOpen = false"></div>
    </Transition>

    <!-- ============ 内容区 ============ -->
    <div class="shell__main">
      <header class="topbar">
        <button
          type="button"
          class="topbar__menu"
          :aria-expanded="drawerOpen"
          aria-label="打开导航菜单"
          @click="drawerOpen = !drawerOpen"
        >
          <span></span><span></span><span></span>
        </button>

        <div class="topbar__crumb">
          <span class="topbar__num">{{ currentNav }}</span>
          <span class="topbar__sep">/</span>
          <span class="topbar__title">{{ currentTitle }}</span>
        </div>

        <div class="spacer"></div>

        <div class="topbar__user">
          <span class="avatar" aria-hidden="true">{{ auth.initials }}</span>
          <span class="topbar__name truncate">{{ auth.displayName }}</span>
        </div>

        <button
          type="button"
          class="btn btn--ghost btn--sm"
          :disabled="loggingOut"
          @click="onLogout"
        >
          <span v-if="loggingOut" class="spinner"></span>
          <span>{{ loggingOut ? '退出中' : '登出' }}</span>
        </button>
      </header>

      <main id="main-content" class="shell__content">
        <RouterView v-slot="{ Component }">
          <Transition name="route-fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  position: relative;
  z-index: 1;
  display: flex;
  min-height: 100vh;
}

/* ---------------- 侧边栏 ---------------- */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 60;
  width: var(--sidebar-w);
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0e121b 0%, var(--bg) 100%);
  border-right: 1px solid var(--line);
}

.sidebar__brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 17px 18px 15px;
}

.brand__dot {
  position: relative;
  flex: none;
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border: 1px solid var(--accent-line);
  border-radius: var(--r-sm);
  background: var(--accent-dim);
}

.brand__dot i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 10px var(--accent), 0 0 0 3px rgba(255, 105, 0, 0.16);
  animation: ledPulse 2.6s var(--ease) infinite;
}

.brand__name {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.brand__sub {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 500;
  letter-spacing: 0.16em;
  color: var(--text-mute);
}

.sidebar__nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.navitem {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 11px;
  border: 1px solid transparent;
  border-radius: var(--r-md);
  color: var(--text-dim);
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease),
    border-color var(--dur-fast) var(--ease);
}

.navitem:hover {
  background: var(--panel);
  color: var(--text);
  border-color: var(--line);
}

.navitem--active {
  background: var(--panel-2);
  border-color: var(--line-strong);
  color: var(--text);
}

/* 活跃项左侧橙条 */
.navitem--active::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--accent);
  border-radius: 0 3px 3px 0;
  box-shadow: 0 0 12px var(--accent);
}

.navitem__num {
  flex: none;
  width: 20px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.04em;
  color: var(--text-mute);
}

.navitem--active .navitem__num {
  color: var(--accent);
}

.navitem__body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.navitem__label {
  font-size: 13.5px;
  font-weight: 500;
  line-height: 1.35;
}

.navitem__hint {
  font-size: 10.5px;
  color: var(--text-mute);
  line-height: 1.4;
}

.sidebar__foot {
  padding: 12px 16px 16px;
  border-top: 1px solid var(--line-soft);
}

.sidebar__status {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ---------------- 主区 ---------------- */
.shell__main {
  flex: 1;
  min-width: 0;
  margin-left: var(--sidebar-w);
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 12px;
  height: var(--topbar-h);
  padding: 0 22px;
  background: rgba(11, 14, 20, 0.82);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
}

/* 顶栏底部的橙色信号渐变线 */
.topbar::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: linear-gradient(90deg, var(--accent) 0%, rgba(255, 105, 0, 0.18) 22%, transparent 52%);
}

.topbar__menu {
  display: none;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 30px;
  height: 30px;
  padding: 0 7px;
  background: transparent;
  border: 1px solid var(--line);
  border-radius: var(--r-sm);
  cursor: pointer;
}

.topbar__menu span {
  display: block;
  height: 1.5px;
  background: var(--text-dim);
  border-radius: 2px;
}

.topbar__menu span:nth-child(2) {
  width: 70%;
}

.topbar__crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.topbar__num {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  color: var(--accent);
}

.topbar__sep {
  color: var(--text-mute);
  font-family: var(--font-mono);
  font-size: 11px;
}

.topbar__title {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text);
}

.topbar__user {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 190px;
}

.avatar {
  flex: none;
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  background: var(--accent-dim);
  border: 1px solid var(--accent-line);
  border-radius: 50%;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-hover);
}

.topbar__name {
  font-size: 13px;
  color: var(--text-dim);
}

.shell__content {
  flex: 1;
  min-width: 0;
}

.scrim {
  position: fixed;
  inset: 0;
  z-index: 55;
  background: rgba(4, 6, 11, 0.7);
  backdrop-filter: blur(3px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 180ms var(--ease);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ---------------- 响应式：≤920px 抽屉 ---------------- */
@media (max-width: 920px) {
  .sidebar {
    transform: translateX(-100%);
    transition: transform 240ms var(--ease);
    box-shadow: var(--shadow-3);
  }
  .sidebar--open {
    transform: translateX(0);
  }
  .shell__main {
    margin-left: 0;
  }
  .topbar {
    padding: 0 14px;
  }
  .topbar__menu {
    display: flex;
  }
  .topbar__user {
    max-width: 120px;
  }
  .topbar__name {
    display: none;
  }
}
</style>
