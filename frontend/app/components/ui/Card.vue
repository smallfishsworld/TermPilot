<script setup lang="ts">
// Boolean props default to false in Vue, so the default must be stated explicitly.
withDefaults(defineProps<{ title?: string, subtitle?: string, padded?: boolean }>(), { padded: true })
</script>

<template>
  <section class="panel">
    <header v-if="title || $slots.actions" class="flex items-start justify-between gap-3 px-5 pt-4">
      <div>
        <h2 v-if="title" class="text-sm font-semibold text-ink">{{ title }}</h2>
        <p v-if="subtitle" class="mt-0.5 text-xs text-muted">{{ subtitle }}</p>
      </div>
      <div class="flex shrink-0 items-center gap-2"><slot name="actions" /></div>
    </header>
    <div :class="padded ? 'p-5' : ''">
      <slot />
    </div>
  </section>
</template>
