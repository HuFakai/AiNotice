<script setup>
/**
 * MultiSelect 下拉多选组件（「信号控制台」设计系统）
 *
 * 交互（对齐参考 UI）：
 * - 触发框：已选项以标签（tag ×）展示；点击开合下拉面板
 * - 下拉面板：选项行 = 标签 + 右侧类型徽章 + 选中 ✓；点击切换选中（面板保持展开）
 * - 点击组件外部自动关闭；Esc 关闭
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  /* options: [{ value, label, badge?, danger? }] */
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择' },
  emptyText: { type: String, default: '暂无可选项' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const rootEl = ref(null)

const selected = computed(() =>
  props.modelValue
    .map((v) => props.options.find((o) => o.value === v))
    .filter(Boolean),
)

function isSelected(option) {
  return props.modelValue.includes(option.value)
}

function toggleOpen() {
  if (props.disabled || props.loading) return
  open.value = !open.value
}

function choose(option) {
  const next = isSelected(option)
    ? props.modelValue.filter((v) => v !== option.value)
    : [...props.modelValue, option.value]
  emit('update:modelValue', next)
}

function removeTag(option) {
  emit('update:modelValue', props.modelValue.filter((v) => v !== option.value))
}

function onDocClick(e) {
  if (rootEl.value && !rootEl.value.contains(e.target)) open.value = false
}

function onKeydown(e) {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div ref="rootEl" class="mselect" :class="{ 'mselect--open': open, 'mselect--disabled': disabled }">
    <button
      type="button"
      class="mselect__trigger"
      :disabled="disabled || loading"
      @click="toggleOpen"
    >
      <span v-if="loading" class="mselect__placeholder">加载中…</span>
      <span v-else-if="!selected.length" class="mselect__placeholder">{{ placeholder }}</span>
      <span v-else class="mselect__tags">
        <span v-for="opt in selected" :key="opt.value" class="mselect__tag">
          {{ opt.label }}
          <span
            v-if="!disabled"
            class="mselect__tag-x"
            role="button"
            aria-label="移除"
            @click.stop="removeTag(opt)"
          >×</span>
        </span>
      </span>
      <span class="mselect__arrow" aria-hidden="true">{{ open ? '⌃' : '⌄' }}</span>
    </button>

    <div v-if="open" class="mselect__panel" role="listbox">
      <div v-if="!options.length" class="mselect__empty">{{ emptyText }}</div>
      <button
        v-for="opt in options"
        :key="opt.value"
        type="button"
        class="mselect__option"
        :class="{ 'mselect__option--on': isSelected(opt), 'mselect__option--danger': opt.danger }"
        role="option"
        :aria-selected="isSelected(opt)"
        @click="choose(opt)"
      >
        <span class="mselect__option-label">{{ opt.label }}</span>
        <span v-if="opt.badge" class="mselect__option-badge">{{ opt.badge }}</span>
        <span v-if="opt.danger" class="badge badge--warn">已禁用</span>
        <span v-if="isSelected(opt)" class="mselect__check" aria-hidden="true">✓</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.mselect {
  position: relative;
}

.mselect__trigger {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;
  min-height: 40px;
  padding: 6px 34px 6px 10px;
  text-align: left;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--line);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.mselect__trigger:hover:not(:disabled),
.mselect--open .mselect__trigger {
  border-color: rgba(255, 105, 0, 0.55);
}

.mselect__trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.mselect__placeholder {
  color: var(--text-dim);
  font-size: 13px;
}

.mselect__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mselect__tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 6px 3px 10px;
  font-size: 12.5px;
  color: var(--text);
  background: rgba(255, 105, 0, 0.12);
  border: 1px solid rgba(255, 105, 0, 0.35);
  border-radius: 6px;
}

.mselect__tag-x {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  color: var(--text-dim);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  transition: color 0.12s ease, background 0.12s ease;
}

.mselect__tag-x:hover {
  color: var(--signal-red);
  background: rgba(255, 92, 92, 0.12);
}

.mselect__arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-dim);
  font-family: var(--font-mono);
  font-size: 13px;
}

.mselect__panel {
  position: absolute;
  z-index: 60;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  max-height: 240px;
  overflow-y: auto;
  padding: 6px;
  background: var(--panel-2, #1a2030);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.5);
}

.mselect__empty {
  padding: 12px;
  font-size: 12.5px;
  color: var(--text-dim);
  text-align: center;
}

.mselect__option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 9px 10px;
  text-align: left;
  font-size: 13px;
  color: var(--text);
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s ease;
}

.mselect__option:hover {
  background: rgba(255, 255, 255, 0.05);
}

.mselect__option--on {
  background: rgba(255, 105, 0, 0.08);
}

.mselect__option--danger {
  opacity: 0.65;
}

.mselect__option-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mselect__option-badge {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--accent);
  letter-spacing: 0.04em;
}

.mselect__check {
  color: var(--accent);
  font-weight: 600;
}
</style>
