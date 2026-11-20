<script setup lang="ts">
import { ListPlus } from '@lucide/vue'
import type { MailDetail, TaskCandidate } from '~/types/api'
import { useMailStore } from '~/stores/mail'
import { usePlannerStore } from '~/stores/planner'
import { useToasts } from '~/stores/toasts'
import { formatDateTime } from '~/utils/format'

const props = defineProps<{ message: MailDetail | null }>()
const open = defineModel<boolean>('open', { default: false })
const mail = useMailStore()
const planner = usePlannerStore()
const toasts = useToasts()
const candidates = ref<TaskCandidate[] | null>(null)
const chosen = ref<Set<number>>(new Set())
const loading = ref(false)
const saving = ref(false)

watch(open, async (value) => {
  if (!value || !props.message) return
  candidates.value = null
  loading.value = true
  try {
    candidates.value = await mail.findTasks(props.message.id)
    chosen.value = new Set(candidates.value.map((_, index) => index))
  }
  catch (error) {
    toasts.failure(error)
    open.value = false
  }
  finally {
    loading.value = false
  }
})

function toggle(index: number) {
  const next = new Set(chosen.value)
  if (next.has(index)) next.delete(index)
  else next.add(index)
  chosen.value = next
}

async function add() {
  saving.value = true
  try {
    const picked = (candidates.value ?? []).filter((_, index) => chosen.value.has(index))
    for (const item of picked) {
      await planner.saveTask({
        title: item.title,
        due_at: item.due_at,
        category: item.category,
        notes: [item.notes, props.message?.subject ? `From email: ${props.message.subject}` : null].filter(Boolean).join('\n') || null,
      })
    }
    toasts.success(`Added ${picked.length} task(s).`)
    open.value = false
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <UiDialog v-model:open="open" title="Deadlines in this email" description="Review what was found before adding it to your tasks.">
    <p v-if="loading" class="text-sm text-muted">Reading the message…</p>
    <UiEmpty v-else-if="candidates && !candidates.length" :icon="ListPlus" title="No dated tasks found" text="Nothing in this message has a clear deadline." />
    <ul v-else-if="candidates" class="divide-y divide-line rounded-xl border border-line">
      <li v-for="(item, index) in candidates" :key="index">
        <label class="flex cursor-pointer items-start gap-3 px-3 py-3 hover:bg-surface-muted">
          <input type="checkbox" class="mt-1 size-4 accent-[var(--tp-brand)]" :checked="chosen.has(index)" @change="toggle(index)">
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-medium">{{ item.title }}</span>
            <span class="block text-xs text-muted">due {{ formatDateTime(item.due_at) }}<template v-if="item.category"> · {{ item.category }}</template></span>
            <span v-if="item.notes" class="mt-1 block text-xs text-muted">{{ item.notes }}</span>
          </span>
        </label>
      </li>
    </ul>
    <template #footer>
      <UiButton @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :disabled="!chosen.size || !candidates?.length" :loading="saving" @click="add">Add to tasks</UiButton>
    </template>
  </UiDialog>
</template>
