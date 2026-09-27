<script setup>
/**
 * 全局 Toast 容器（渲染 lib/toast.js 的响应式队列）
 */
import { dismiss, toastState } from '../lib/toast.js'
</script>

<template>
  <div class="toast-layer" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div
        v-for="item in toastState.items"
        :key="item.id"
        class="toast"
        :class="`toast--${item.type}`"
        @click="dismiss(item.id)"
      >
        <span class="led" :class="`led--${item.type === 'success' ? 'success' : item.type === 'warn' ? 'warn' : item.type === 'error' ? 'error' : 'info'}`" aria-hidden="true"></span>

        <div class="toast__body">
          <div class="toast__title">{{ item.title }}</div>
          <div class="toast__msg">{{ item.message }}</div>
        </div>

        <button type="button" class="toast__close" aria-label="关闭提示" @click.stop="dismiss(item.id)">
          ×
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast .led {
  margin-top: 5px;
}
</style>
