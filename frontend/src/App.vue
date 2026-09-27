<script setup>
/**
 * 应用根组件
 * - 承载全局 Toast 层
 * - 首个受保护路由渲染前完成一次会话恢复（fetchMe）
 */
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import Toast from './components/Toast.vue'
import { useAuthStore } from './stores/auth.js'

const auth = useAuthStore()
const route = useRoute()
const booting = ref(true)

onMounted(async () => {
  try {
    await auth.bootstrap()
  } finally {
    booting.value = false
  }
})
</script>

<template>
  <div class="app-root">
    <!-- 恢复会话期间只在受保护路由展示启动态，登录/注册页直接渲染 -->
    <div v-if="booting && !route.meta?.public" class="boot-screen">
      <div class="boot-screen__mark">
        <span class="led led--active led--pulse"></span>
        <span class="tag-mono">AINOTICE · 正在建立链路</span>
      </div>
      <div class="boot-screen__bar"><i></i></div>
    </div>

    <RouterView v-else v-slot="{ Component }">
      <Transition name="route-fade" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>

    <Toast />
  </div>
</template>

<style scoped>
.app-root {
  min-height: 100%;
  position: relative;
}

.boot-screen {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  background: var(--bg);
}

.boot-screen__mark {
  display: flex;
  align-items: center;
  gap: 10px;
}

.boot-screen__bar {
  position: relative;
  width: 210px;
  height: 2px;
  background: var(--line);
  border-radius: 999px;
  overflow: hidden;
}

.boot-screen__bar i {
  position: absolute;
  inset: 0;
  width: 34%;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  animation: signalSweep 1.1s var(--ease) infinite;
}
</style>
