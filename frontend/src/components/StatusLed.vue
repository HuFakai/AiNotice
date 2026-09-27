<script setup>
/**
 * LED 状态点
 * - 状态一律用带光晕的圆点表达
 * - tone: success / error / warn / info / active / offline
 * - pulse 仅用于「等待 / 进行中」这类真正动态的状态
 */
import { computed } from 'vue'

const props = defineProps({
  tone: { type: String, default: 'offline' },
  pulse: { type: Boolean, default: false },
  size: { type: Number, default: 8 },
  /** 附带文字标签 */
  label: { type: String, default: '' },
  /** 文字颜色随状态 */
  colored: { type: Boolean, default: true },
})

const toneClass = computed(() => `led--${props.tone || 'offline'}`)
const style = computed(() => ({ width: `${props.size}px`, height: `${props.size}px` }))
</script>

<template>
  <span v-if="label" class="led-inline">
    <span class="led" :class="[toneClass, { 'led--pulse': pulse }]" :style="style" aria-hidden="true"></span>
    <span class="led-inline__label" :class="{ 'led-inline__label--muted': !colored }">{{ label }}</span>
  </span>
  <span v-else class="led" :class="[toneClass, { 'led--pulse': pulse }]" :style="style" aria-hidden="true"></span>
</template>

<style scoped>
.led-inline {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
}

.led-inline__label {
  font-size: 12.5px;
  color: var(--text-dim);
}

.led-inline__label--muted {
  color: var(--text-dim);
}
</style>
