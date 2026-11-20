<script setup lang="ts">
import { CalendarPlus, Check, ListChecks, Plus } from '@lucide/vue'
import type { Task } from '~/types/api'
import { usePlannerStore } from '~/stores/planner'
import { useToasts } from '~/stores/toasts'
import { formatDateTime, formatMinutes, relativeTime } from '~/utils/format'

useHead({ title: 'Tasks · TermPilot' })

const planner = usePlannerStore()
const toasts = useToasts()
const filter = ref<'open' | 'done' | 'all'>('open')
const search = ref('')
const editing = ref<Task | null>(null)
const dialogs = reactive({ task: false, plan: false })

const ORIGIN_LABEL: Record<string, string> = { lms: 'Learning platform', manual: 'Added by you', assistant: 'Assistant', mail: 'From email' }

const visible = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return planner.tasks
    .filter(task => filter.value === 'all' || (filter.value === 'done' ? task.done : !task.done))
    .filter(task => !needle || `${task.title} ${task.course ?? ''}`.toLowerCase().includes(needle))
    .sort((a, b) => a.due_at.localeCompare(b.due_at))
})

const groups = computed(() => {
  const now = Date.now()
  const endOfToday = new Date()
  endOfToday.setHours(23, 59, 59, 999)
  const endOfWeek = now + 7 * 86_400_000
  const buckets: { key: string, title: string, items: Task[] }[] = [
    { key: 'overdue', title: 'Overdue', items: [] },
    { key: 'today', title: 'Today', items: [] },
    { key: 'week', title: 'Next 7 days', items: [] },
    { key: 'later', title: 'Later', items: [] },
    { key: 'done', title: 'Done', items: [] },
  ]
  for (const task of visible.value) {
    const due = new Date(task.due_at).getTime()
    const key = task.done ? 'done' : due < now ? 'overdue' : due <= endOfToday.getTime() ? 'today' : due <= endOfWeek ? 'week' : 'later'
    buckets.find(bucket => bucket.key === key)!.items.push(task)
  }
  return buckets.filter(bucket => bucket.items.length)
})

const openEffort = computed(() => planner.openTasks.reduce((sum, task) => sum + (task.effort_minutes ?? 0), 0))

function edit(task: Task | null) {
  editing.value = task
  dialogs.task = true
}

async function toggle(task: Task) {
  try {
    await planner.toggleDone(task)
  }
  catch (error) {
    toasts.failure(error)
  }
}

onMounted(() => planner.loadTasks().catch(toasts.failure))
</script>

<template>
  <div>
    <AppPageHeading title="Tasks" :subtitle="`${planner.openTasks.length} open${openEffort ? ` · about ${formatMinutes(openEffort)} estimated` : ''}`">
      <UiButton @click="dialogs.plan = true"><CalendarPlus class="size-4" /> Plan study time</UiButton>
      <UiButton variant="primary" @click="edit(null)"><Plus class="size-4" /> New task</UiButton>
    </AppPageHeading>

    <div class="mb-4 flex flex-wrap items-center gap-3">
      <UiSegmented v-model="filter" :options="[{ value: 'open', label: 'Open' }, { value: 'done', label: 'Done' }, { value: 'all', label: 'All' }]" />
      <input v-model="search" class="input max-w-xs" type="search" placeholder="Filter by title or course">
    </div>

    <UiCard v-if="!groups.length" :padded="false">
      <UiEmpty :icon="ListChecks" :title="filter === 'done' ? 'Nothing finished yet' : 'No tasks here'" text="Deadlines from the learning platform appear after a sync. You can also add your own." />
    </UiCard>

    <div class="space-y-6">
      <section v-for="group in groups" :key="group.key">
        <h2 class="mb-2 text-xs font-semibold tracking-wide uppercase" :class="group.key === 'overdue' ? 'text-danger' : 'text-muted'">
          {{ group.title }} · {{ group.items.length }}
        </h2>
        <ul class="panel divide-y divide-line">
          <li v-for="task in group.items" :key="task.id" class="flex items-center gap-3 px-4 py-3">
            <button
              class="grid size-5 shrink-0 place-items-center rounded-md border transition"
              :class="task.done ? 'border-ok bg-ok text-white dark:text-page' : 'border-line hover:border-brand'"
              :aria-label="task.done ? 'Mark as not done' : 'Mark as done'"
              @click="toggle(task)"
            >
              <Check v-if="task.done" class="size-3.5" />
            </button>
            <button class="min-w-0 flex-1 text-left" @click="edit(task)">
              <p class="truncate text-sm font-medium" :class="task.done ? 'text-muted line-through' : ''">{{ task.title }}</p>
              <p class="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted">
                <span v-if="task.course">{{ task.course }}</span>
                <span :title="formatDateTime(task.due_at)">{{ formatDateTime(task.due_at) }} ({{ relativeTime(task.due_at) }})</span>
                <span>{{ ORIGIN_LABEL[task.origin] ?? task.origin }}</span>
                <span v-if="task.effort_minutes">~{{ formatMinutes(task.effort_minutes) }}</span>
              </p>
            </button>
            <UiBadge v-if="task.category === 'exam'" tone="accent">exam</UiBadge>
            <UiBadge v-if="task.priority === 'high'" tone="warn">high</UiBadge>
            <UiBadge v-else-if="task.priority === 'low'">low</UiBadge>
          </li>
        </ul>
      </section>
    </div>

    <PlannerTaskDialog v-model:open="dialogs.task" :task="editing" />
    <PlannerStudyPlanDialog v-model:open="dialogs.plan" />
  </div>
</template>
