<script setup>
/**
 * 指标卡：mono 大数字 + LED + 600ms 数字滚动
 * 参考视觉：设备仪表读数
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  /** 数值；传 null/undefined 显示占位符 */
  value: { type: [Number, String], default: null },
  unit: { type: String, default: '' },
  /** 小数位；null 表示按整数展示并加千分位 */
  digits: { type: Number, default: null },
  tone: { type: String, default: '' },
  pulse: { type: Boolean, default: false },
  hint: { type: String, default: '' },
  accent: { type: Boolean, default: false },
  /** 是否对数字做滚动动画 */
  animate: { type: Boolean, default: true },
})

const prefersReducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

const numericTarget = computed(() => {
  const n = Number(props.value)
  return Number.isFinite(n) ? n : null
})

const animated = ref(numericTarget.value)
let raf = null

function stop() {
  if (raf) {
    cancelAnimationFrame(raf)
    raf = null
  }
}

function runAnimation(to) {
  stop()
  if (!props.animate || prefersReducedMotion) {
    animated.value = to
    return
  }

  const from = Number.isFinite(Number(animated.value)) ? Number(animated.value) : 0
  const start = performance.now()
  const duration = 600

  const step = (now) => {
    const t = Math.min(1, (now - start) / duration)
    // easeOutCubic：读数起步快、收尾稳
    const eased = 1 - Math.pow(1 - t, 3)
    animated.value = from + (to - from) * eased
    if (t < 1) raf = requestAnimationFrame(step)
    else {
      animated.value = to
      raf = null
    }
  }
  raf = requestAnimationFrame(step)
}

watch(numericTarget, (to) => {
  if (to === null) {
    animated.value = null
    stop()
    return
  }
  runAnimation(to)
}, { immediate: true })

onBeforeUnmount(stop)

const display = computed(() => {
  const source = props.animate ? animated.value : numericTarget.value
  if (source === null || source === undefined) {
    // 非数字（如 "99.9%" 这类预格式化字符串）直接原样展示
    if (props.value === null || props.value === undefined || props.value === '') return '—'
    return String(props.value)
  }
  const n = Number(source)
  if (!Number.isFinite(n)) return '—'
  if (props.digits !== null) return n.toFixed(props.digits)
  return Math.round(n).toLocaleString('zh-CN')
})

const toneClass = computed(() => (props.tone ? `text-${props.tone}` : ''))
</script>

<template>
  <div class="stat" :class="{ 'stat--accent': accent }">
    <div class="stat__top">
      <span class="stat__label">{{ label }}</span>
      <span v-if="tone" class="led" :class="[`led--${tone}`, { 'led--pulse': pulse }]" aria-hidden="true"></span>
    </div>

    <div class="stat__value" :class="toneClass">
      <span>{{ display }}</span>
      <span v-if="unit" class="stat__unit">{{ unit }}</span>
    </div>

    <div v-if="hint" class="stat__foot">{{ hint }}</div>
  </div>
</template>
