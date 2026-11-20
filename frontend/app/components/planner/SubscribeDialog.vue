<script setup lang="ts">
import { Copy, Download } from '@lucide/vue'
import { usePlannerStore } from '~/stores/planner'
import { useToasts } from '~/stores/toasts'

const open = defineModel<boolean>('open', { default: false })
const planner = usePlannerStore()
const toasts = useToasts()
const link = ref<{ url: string, expires_in_days: number } | null>(null)

watch(open, async (value) => {
  if (!value || link.value) return
  try {
    link.value = await planner.calendarLink()
  }
  catch (error) {
    toasts.failure(error)
  }
})

async function copy() {
  if (!link.value) return
  await navigator.clipboard.writeText(link.value.url)
  toasts.success('Link copied.')
}
</script>

<template>
  <UiDialog v-model:open="open" title="Add to your calendar" description="Classes for the whole term and your open deadlines, as a private calendar feed.">
    <div v-if="link" class="space-y-4 text-sm">
      <div class="flex gap-2">
        <input class="input font-mono text-xs" :value="link.url" readonly @focus="($event.target as HTMLInputElement).select()">
        <UiButton @click="copy"><Copy class="size-4" /> Copy</UiButton>
      </div>
      <ul class="space-y-2 text-muted">
        <li><b class="text-ink">Google Calendar:</b> Other calendars → From URL.</li>
        <li><b class="text-ink">Apple Calendar:</b> File → New Calendar Subscription.</li>
        <li><b class="text-ink">Outlook:</b> Add calendar → Subscribe from web.</li>
      </ul>
      <p class="rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">
        Anyone with this link can read your schedule. It stops working when you sign out or after {{ link.expires_in_days }} days.
      </p>
      <a :href="link.url" class="inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline" download="termpilot.ics">
        <Download class="size-4" /> Download once instead (.ics)
      </a>
    </div>
    <p v-else class="text-sm text-muted">Preparing your link…</p>
  </UiDialog>
</template>
