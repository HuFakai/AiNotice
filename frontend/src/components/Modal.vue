<script setup>
/**
 * 模态框
 * - 仅通过 prop 控制，关闭时 emit('close')
 * - lockClose=true 时屏蔽遮罩点击与 ESC（用于「密钥已创建」这类强制确认场景）
 * - Teleport 到 body，避免被父级 overflow/transform 裁剪
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  sub: { type: String, default: '' },
  size: { type: String, default: 'md' }, // sm | md | lg
  lockClose: { type: Boolean, default: false },
  /** 点击遮罩是否可关闭 */
  closeOnBackdrop: { type: Boolean, default: true },
})

const emit = defineEmits(['close'])
const panel = ref(null)
let lastFocused = null

function requestClose() {
  if (props.lockClose) return
  emit('close')
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (!props.lockClose) emit('close')
    return
  }
  // 焦点锁在模态内部
  if (e.key === 'Tab' && panel.value) {
    const nodes = panel.value.querySelectorAll(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
    if (!nodes.length) return
    const list = Array.from(nodes)
    const first = list[0]
    const last = list[list.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }
}

function syncBodyLock() {
  if (typeof document === 'undefined') return
  const anyOpen = document.querySelector('.modal-backdrop')
  document.body.style.overflow = props.open || anyOpen ? 'hidden' : ''
}

watch(
  () => props.open,
  (open) => {
    if (typeof document === 'undefined') return
    if (open) {
      lastFocused = document.activeElement
      document.addEventListener('keydown', onKeydown)
      requestAnimationFrame(() => {
        const target = panel.value?.querySelector(
          '[data-autofocus], button:not(.modal__close), input, textarea, select'
        )
        if (target && typeof target.focus === 'function') target.focus()
        else panel.value?.focus?.()
      })
    } else {
      document.removeEventListener('keydown', onKeydown)
      if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus()
    }
    syncBodyLock()
  }
)

onMounted(syncBodyLock)
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  syncBodyLock()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="modal-backdrop"
        @click.self="closeOnBackdrop && requestClose()"
      >
        <div
          ref="panel"
          class="modal"
          :class="{ 'modal--sm': size === 'sm', 'modal--lg': size === 'lg' }"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          tabindex="-1"
        >
          <div class="modal__head">
            <div class="modal__headText">
              <h2 class="modal__title">{{ title }}</h2>
              <p v-if="sub" class="modal__sub">{{ sub }}</p>
            </div>
            <button
              v-if="!lockClose"
              type="button"
              class="modal__close"
              aria-label="关闭"
              @click="requestClose"
            >
              ×
            </button>
          </div>

          <div class="modal__body">
            <slot />
          </div>

          <div v-if="$slots.footer" class="modal__foot">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal__headText {
  min-width: 0;
}
</style>
