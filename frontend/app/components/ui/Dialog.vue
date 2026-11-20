<script setup lang="ts">
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle } from 'reka-ui'
import { X } from '@lucide/vue'

withDefaults(defineProps<{ title: string, description?: string, wide?: boolean }>(), { wide: false })
const open = defineModel<boolean>('open', { default: false })
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogPortal>
      <DialogOverlay class="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-[2px]" />
      <DialogContent
        class="panel fixed top-1/2 left-1/2 z-50 flex max-h-[88vh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col shadow-xl focus:outline-none"
        :class="wide ? 'max-w-3xl' : 'max-w-lg'"
      >
        <header class="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <DialogTitle class="text-base font-semibold">{{ title }}</DialogTitle>
            <DialogDescription v-if="description" class="mt-1 text-sm text-muted">{{ description }}</DialogDescription>
          </div>
          <DialogClose class="rounded-md p-1 text-muted hover:bg-surface-muted hover:text-ink" aria-label="Close">
            <X class="size-4" />
          </DialogClose>
        </header>
        <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="flex justify-end gap-2 border-t border-line px-5 py-3">
          <slot name="footer" />
        </footer>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>
