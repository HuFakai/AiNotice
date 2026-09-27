<script setup>
/**
 * 页头：带 2px 橙色渐变「信号线」签名元素
 */
const props = defineProps({
  title: { type: String, required: true },
  desc: { type: String, default: '' },
  /** 左上角等宽小标（如 01 · DASHBOARD） */
  eyebrow: { type: String, default: '' },
  nav: { type: String, default: '' },
})
</script>

<template>
  <header class="page-head">
    <div class="page-head__top">
      <div class="page-head__text">
        <div v-if="eyebrow || nav" class="page-head__eyebrow">
          <span v-if="nav">{{ nav }}</span>
          <span v-if="nav && eyebrow" class="page-head__sep">/</span>
          <span v-if="eyebrow">{{ eyebrow }}</span>
        </div>
        <h1 class="page-head__title">{{ title }}</h1>
        <p v-if="desc" class="page-head__desc">{{ desc }}</p>
      </div>

      <div v-if="$slots.actions" class="page-head__actions">
        <slot name="actions" />
      </div>
    </div>
  </header>
</template>

<style scoped>
.page-head__text {
  min-width: 0;
}

.page-head__sep {
  color: var(--text-mute);
}
</style>
