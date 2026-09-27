<script setup>
/**
 * 确认对话框（危险操作二次确认）
 */
import Modal from './Modal.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '' },
  /** 需要用户逐字确认的危险输入（如输入密钥名）。留空则不显示 */
  confirmWord: { type: String, default: '' },
  confirmText: { type: String, default: '确认' },
  cancelText: { type: String, default: '取消' },
  danger: { type: Boolean, default: true },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel', 'update:open'])

const typed = defineModel('typed', { type: String, default: '' })
</script>

<template>
  <Modal
    :open="open"
    :title="title"
    size="sm"
    :lock-close="loading"
    @close="emit('cancel')"
  >
    <p class="confirm__msg">{{ message }}</p>

    <div v-if="confirmWord" class="field mt-3">
      <label class="field__label">
        请输入 <code class="confirm__word">{{ confirmWord }}</code> 以确认
      </label>
      <input v-model="typed" class="input input--mono" :placeholder="confirmWord" autocomplete="off" />
    </div>

    <template #footer>
      <button type="button" class="btn btn--ghost" :disabled="loading" @click="emit('cancel')">
        {{ cancelText }}
      </button>
      <button
        type="button"
        class="btn"
        :class="danger ? 'btn--danger' : 'btn--primary'"
        :disabled="loading || (confirmWord && typed !== confirmWord)"
        @click="emit('confirm')"
      >
        <span v-if="loading" class="spinner"></span>
        <span>{{ loading ? '处理中' : confirmText }}</span>
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.confirm__msg {
  font-size: 13.5px;
  color: var(--text-dim);
  line-height: 1.7;
  white-space: pre-line;
}

.confirm__word {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent-hover);
  background: var(--accent-dim);
  padding: 1px 5px;
  border-radius: 4px;
}
</style>
