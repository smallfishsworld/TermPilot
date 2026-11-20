<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{ icon?: Component, title: string, text?: string }>()
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
    <div v-if="icon" class="mb-1 grid size-11 place-items-center rounded-xl bg-surface-muted text-muted">
      <component :is="icon" class="size-5" />
    </div>
    <p class="text-sm font-medium text-ink">{{ title }}</p>
    <p v-if="text" class="max-w-sm text-sm text-muted">{{ text }}</p>
    <div v-if="$slots.default" class="mt-2"><slot /></div>
  </div>
</template>
