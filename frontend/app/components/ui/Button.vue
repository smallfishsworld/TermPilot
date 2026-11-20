<script setup lang="ts">
import { LoaderCircle } from '@lucide/vue'

const props = withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  loading?: boolean
  disabled?: boolean
  type?: 'button' | 'submit'
  block?: boolean
}>(), { variant: 'secondary', size: 'md', type: 'button' })

const classes = computed(() => [
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition select-none disabled:cursor-not-allowed disabled:opacity-55',
  props.size === 'sm' ? 'h-8 px-3 text-xs' : 'h-10 px-4 text-sm',
  props.block ? 'w-full' : '',
  {
    primary: 'bg-brand text-white shadow-sm hover:bg-brand-strong dark:text-page',
    secondary: 'border border-line bg-surface text-ink hover:bg-surface-muted',
    ghost: 'text-muted hover:bg-surface-muted hover:text-ink',
    danger: 'bg-danger text-white hover:opacity-90 dark:text-page',
  }[props.variant],
])
</script>

<template>
  <button :type="type" :class="classes" :disabled="disabled || loading">
    <LoaderCircle v-if="loading" class="size-4 animate-spin" aria-hidden="true" />
    <slot />
  </button>
</template>
