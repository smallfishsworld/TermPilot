<script setup lang="ts">
const props = withDefaults(defineProps<{ tone?: 'neutral' | 'brand' | 'accent' | 'warn' | 'danger' | 'ok' }>(), { tone: 'neutral' })

const toneClass = computed(() => ({
  neutral: 'bg-surface-muted text-muted',
  brand: 'bg-brand-soft text-brand-strong',
  accent: 'bg-accent-soft text-accent',
  warn: 'bg-warn-soft text-warn',
  danger: 'bg-danger-soft text-danger',
  ok: 'bg-ok-soft text-ok',
}[props.tone]))
</script>

<template>
  <span class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[0.7rem] font-semibold tracking-wide" :class="toneClass">
    <slot />
  </span>
</template>
