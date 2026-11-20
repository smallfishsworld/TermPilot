<script setup lang="ts" generic="T extends string">
defineProps<{ options: { value: T, label: string, hint?: string }[] }>()
const model = defineModel<T>({ required: true })
</script>

<template>
  <div class="inline-flex rounded-lg border border-line bg-surface-muted p-0.5" role="radiogroup">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="model === option.value"
      :title="option.hint"
      class="rounded-md px-3 py-1 text-xs font-medium transition"
      :class="model === option.value ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink'"
      @click="model = option.value"
    >
      {{ option.label }}
    </button>
  </div>
</template>
