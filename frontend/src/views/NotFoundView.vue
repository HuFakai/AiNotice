<script setup>
/**
 * 404 页面
 * 不区分登录态：给出返回控制台/登录的出口。
 */
import { computed } from 'vue'

import { getToken } from '../api/client.js'

const authed = computed(() => Boolean(getToken()))
</script>

<template>
  <div class="nf">
    <div class="nf__card">
      <div class="nf__eyebrow">
        <span class="led led--error" aria-hidden="true"></span>
        <span class="tag-mono">404 · SIGNAL LOST</span>
      </div>

      <h1 class="nf__code mono">404</h1>
      <p class="nf__title">该路径没有对应的端点</p>
      <p class="nf__desc">
        请求的页面不存在或已被移动。如果是刚部署，请确认构建产物已经更新。
      </p>

      <div class="nf__actions">
        <RouterLink v-if="authed" to="/" class="btn btn--primary">返回仪表盘</RouterLink>
        <RouterLink v-else to="/login" class="btn btn--primary">前往登录</RouterLink>
        <RouterLink v-if="authed" to="/api-docs" class="btn btn--ghost">查看接口文档</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nf {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 30px 18px;
}

.nf__card {
  width: 100%;
  max-width: 452px;
  padding: 34px 30px 30px;
  background: var(--panel);
  border: 1px solid var(--line-strong);
  border-radius: var(--r-xl);
  box-shadow: var(--inset-top), var(--shadow-3);
  text-align: center;
  animation: popIn 340ms var(--ease) both;
}

.nf__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 16px;
}

.nf__code {
  font-size: 58px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--accent);
  text-shadow: 0 0 44px rgba(255, 105, 0, 0.34);
}

.nf__title {
  margin-top: 12px;
  font-size: 15px;
  font-weight: 700;
}

.nf__desc {
  margin-top: 7px;
  font-size: 12.5px;
  color: var(--text-mute);
  line-height: 1.7;
}

.nf__actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  margin-top: 22px;
  flex-wrap: wrap;
}
</style>
