<script setup>
/**
 * 空状态：统一的「此处无数据」表达
 */
defineProps({
  title: { type: String, default: '暂无数据' },
  desc: { type: String, default: '' },
  /** 图标字符（纯文本，不使用 HTML） */
  icon: { type: String, default: '∅' },
})
</script>

<template>
  <div class="empty">
    <div class="empty__icon" aria-hidden="true">
      <span class="empty__glyph">{{ icon }}</span>
    </div>
    <div class="empty__title">{{ title }}</div>
    <p v-if="desc" class="empty__desc">{{ desc }}</p>
    <div v-if="$slots.default" class="empty__action">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty__glyph {
  font-family: var(--font-mono);
  font-size: 17px;
  line-height: 1;
}

.empty__action {
  margin-top: 6px;
}
</style>
