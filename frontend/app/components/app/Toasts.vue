<script setup lang="ts">
import { CircleAlert, CircleCheck, Info, X } from '@lucide/vue'
import { useToasts } from '~/stores/toasts'

const toasts = useToasts()
const icons = { info: Info, success: CircleCheck, error: CircleAlert }
</script>

<template>
  <div class="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
    <TransitionGroup
      enter-from-class="translate-y-2 opacity-0"
      enter-active-class="transition duration-200"
      leave-to-class="opacity-0"
      leave-active-class="transition duration-150"
    >
      <div
        v-for="toast in toasts.items"
        :key="toast.id"
        class="panel pointer-events-auto flex items-start gap-3 px-4 py-3 text-sm shadow-lg"
        :class="{ 'border-danger/40': toast.tone === 'error', 'border-ok/40': toast.tone === 'success' }"
        role="status"
      >
        <component
          :is="icons[toast.tone]"
          class="mt-0.5 size-4 shrink-0"
          :class="{ 'text-danger': toast.tone === 'error', 'text-ok': toast.tone === 'success', 'text-brand': toast.tone === 'info' }"
        />
        <p class="flex-1">{{ toast.text }}</p>
        <button class="text-muted hover:text-ink" aria-label="Dismiss" @click="toasts.dismiss(toast.id)"><X class="size-4" /></button>
      </div>
    </TransitionGroup>
  </div>
</template>
