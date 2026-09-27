<script setup>
/**
 * 复制按钮：copy 成功后 1.6s 内显示 ✓ 已复制
 * 不写死要复制的内容来源，由父级传 text（永远走 textContent 通道）
 */
import { onBeforeUnmount, ref } from 'vue'

import { copyText } from '../lib/format.js'
import { toastError } from '../lib/toast.js'

const props = defineProps({
  text: { type: [String, Number], default: '' },
  label: { type: String, default: '复制' },
  copiedLabel: { type: String, default: '已复制' },
  /** 复制成功提示语中的对象名，如「API 密钥」 */
  subject: { type: String, default: '' },
  /** 是否使用 toast 反馈（false 时只做按钮态变化） */
  notify: { type: Boolean, default: false },
})

const copied = ref(false)
let timer = null

async function onCopy() {
  const ok = await copyText(props.text)
  if (!ok) {
    toastError('复制失败，请手动选择文本复制')
    return
  }

  copied.value = true
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    copied.value = false
    timer = null
  }, 1600)
}

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})
</script>

<template>
  <button
    type="button"
    class="copy-btn"
    :class="{ 'is-copied': copied }"
    :title="`复制${subject || '内容'}`"
    @click="onCopy"
  >
    <span aria-hidden="true">{{ copied ? '✓' : '⧉' }}</span>
    <span>{{ copied ? copiedLabel : label }}</span>
  </button>
</template>
