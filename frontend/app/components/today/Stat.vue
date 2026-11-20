<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{ icon: Component, label: string, value: string | number, to?: string, hint?: string }>()
</script>

<template>
  <NuxtLink :to="to ?? ''" class="panel group flex items-center gap-3 p-4 transition hover:border-brand/50" :class="to ? '' : 'pointer-events-none'">
    <div class="grid size-10 place-items-center rounded-xl bg-surface-muted text-muted transition group-hover:bg-brand-soft group-hover:text-brand-strong">
      <component :is="icon" class="size-5" />
    </div>
    <div class="min-w-0">
      <p class="text-xl leading-none font-semibold tabular-nums">{{ value }}</p>
      <p class="mt-1 truncate text-xs text-muted">{{ label }}</p>
      <p v-if="hint" class="truncate text-[0.7rem] text-muted/80">{{ hint }}</p>
    </div>
  </NuxtLink>
</template>
