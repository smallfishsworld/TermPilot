<script setup lang="ts">
import { CalendarPlus, FilePen, ListPlus, Mail, ShieldQuestion } from '@lucide/vue'
import type { Approval } from '~/types/api'
import { useAssistantStore } from '~/stores/assistant'
import { useToasts } from '~/stores/toasts'
import { relativeTime } from '~/utils/format'

const props = defineProps<{ approval: Approval }>()
const assistant = useAssistantStore()
const toasts = useToasts()
const deciding = ref<'approve' | 'reject' | null>(null)

const live = computed(() => assistant.approvals[props.approval.id] ?? props.approval)
const expired = computed(() => live.value.status === 'pending' && new Date(live.value.expires_at).getTime() < Date.now())
const icon = computed(() => {
  if (live.value.kind.startsWith('email')) return Mail
  if (live.value.kind.startsWith('files')) return FilePen
  if (live.value.kind.startsWith('task')) return ListPlus
  if (live.value.kind.startsWith('study') || live.value.kind.startsWith('timetable')) return CalendarPlus
  return ShieldQuestion
})
const tone = computed(() => ({ done: 'ok', failed: 'danger', rejected: 'neutral', expired: 'neutral', running: 'brand', pending: 'warn' } as const)[expired.value ? 'expired' : live.value.status])

async function decide(approve: boolean) {
  deciding.value = approve ? 'approve' : 'reject'
  try {
    const result = await assistant.decide(live.value.id, approve)
    if (result.status === 'done') toasts.success(result.outcome ?? 'Done.')
    else if (result.status === 'failed') toasts.failure(new Error(result.outcome ?? 'The action failed.'))
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    deciding.value = null
  }
}
</script>

<template>
  <div class="rounded-xl border p-4" :class="live.status === 'pending' && !expired ? 'border-warn/40 bg-warn-soft/30' : 'border-line bg-surface-muted/40'">
    <div class="flex items-start gap-3">
      <div class="grid size-9 shrink-0 place-items-center rounded-lg bg-surface text-warn"><component :is="icon" class="size-4" /></div>
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <p class="text-sm font-semibold">{{ live.title }}</p>
          <UiBadge :tone="tone">{{ expired ? 'expired' : live.status === 'pending' ? 'needs your decision' : live.status }}</UiBadge>
        </div>
        <p class="mt-1 text-sm text-muted">{{ live.summary }}</p>
        <pre v-if="live.preview" class="mt-3 max-h-56 overflow-auto rounded-lg border border-line bg-surface p-3 font-mono text-xs whitespace-pre-wrap">{{ live.preview }}</pre>
        <p v-if="live.outcome && live.status !== 'pending'" class="mt-2 text-xs" :class="live.status === 'failed' ? 'text-danger' : 'text-muted'">{{ live.outcome }}</p>
        <div v-if="live.status === 'pending' && !expired" class="mt-3 flex flex-wrap items-center gap-2">
          <UiButton size="sm" variant="primary" :loading="deciding === 'approve'" :disabled="deciding !== null" @click="decide(true)">Approve</UiButton>
          <UiButton size="sm" :loading="deciding === 'reject'" :disabled="deciding !== null" @click="decide(false)">Decline</UiButton>
          <span class="text-xs text-muted">expires {{ relativeTime(live.expires_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
