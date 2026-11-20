<script setup lang="ts">
import { useEventListener } from '@vueuse/core'
import {
  BookOpenText, CalendarClock, CalendarPlus, Clock3, Inbox, Lightbulb, MapPin, RefreshCw, ShieldQuestion, Sparkles, TriangleAlert,
} from '@lucide/vue'
import { useCampusStore } from '~/stores/campus'
import { usePlannerStore } from '~/stores/planner'
import { useSessionStore } from '~/stores/session'
import { useToasts } from '~/stores/toasts'
import { formatDateTime, formatLongDate, greeting, relativeTime } from '~/utils/format'
import type { Task } from '~/types/api'

useHead({ title: 'Today · TermPilot' })

const session = useSessionStore()
const planner = usePlannerStore()
const campus = useCampusStore()
const toasts = useToasts()
const route = useRoute()
const planOpen = ref(false)
const welcome = computed(() => route.query.welcome === '1' && !planner.briefing?.last_sync_at)

const briefing = computed(() => planner.briefing)
// Class times are campus wall-clock times, so compare them with the campus clock
// the API reports (its ISO string carries the campus offset), not the browser's.
const nowMinutes = computed(() => {
  const stamp = briefing.value?.now
  if (!stamp) return new Date().getHours() * 60 + new Date().getMinutes()
  return Number(stamp.slice(11, 13)) * 60 + Number(stamp.slice(14, 16))
})

function status(start: string, end: string) {
  const toMinutes = (value: string) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5))
  if (nowMinutes.value >= toMinutes(end)) return 'past'
  if (nowMinutes.value >= toMinutes(start)) return 'now'
  return 'later'
}

async function load() {
  try {
    await planner.loadBriefing()
  }
  catch (error) {
    toasts.failure(error)
  }
}

async function firstSync() {
  try {
    await campus.sync()
    await load()
    toasts.success('Your semester has been imported.')
  }
  catch (error) {
    toasts.failure(error)
  }
}

async function toggle(task: Task) {
  try {
    await planner.toggleDone(task)
  }
  catch (error) {
    toasts.failure(error)
  }
}

onMounted(load)
useEventListener(window, 'termpilot:synced', load)
</script>

<template>
  <div>
    <AppPageHeading
      :title="`${greeting(Math.floor(nowMinutes / 60))}${session.firstName ? `, ${session.firstName}` : ''}`"
      :subtitle="briefing ? `${formatLongDate(briefing.day)} · ${briefing.term.label}${briefing.term.in_session ? ` · week ${briefing.term.current_week} of ${briefing.term.weeks}` : ''}` : 'Loading your day…'"
    >
      <UiButton @click="planOpen = true"><CalendarPlus class="size-4" /> Plan study time</UiButton>
      <UiButton variant="primary" @click="navigateTo('/assistant')"><Sparkles class="size-4" /> Ask the assistant</UiButton>
    </AppPageHeading>

    <div v-if="welcome" class="panel mb-6 flex flex-wrap items-center gap-4 border-brand/40 bg-brand-soft/40 p-5">
      <div class="flex-1">
        <p class="font-medium">Welcome to TermPilot</p>
        <p class="mt-1 text-sm text-muted">Import your timetable, deadlines and grades from the campus systems to get started. This takes a few seconds.</p>
      </div>
      <UiButton variant="primary" :loading="campus.syncing" @click="firstSync"><RefreshCw class="size-4" /> Import my semester</UiButton>
    </div>

    <div v-if="briefing" class="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <div class="space-y-6">
        <UiCard title="On the timetable today" :subtitle="briefing.classes_today.length ? `${briefing.classes_today.length} on the timetable · ${briefing.classes_tomorrow} tomorrow` : undefined">
          <template #actions>
            <NuxtLink to="/timetable" class="text-xs font-medium text-brand hover:underline">Open timetable</NuxtLink>
          </template>
          <UiEmpty
            v-if="!briefing.classes_today.length"
            :icon="CalendarClock"
            title="No classes today"
            :text="briefing.classes_tomorrow ? `${briefing.classes_tomorrow} tomorrow.` : 'A good day to get ahead on coursework.'"
          />
          <ol v-else class="relative space-y-3 border-l border-line pl-5">
            <li v-for="entry in briefing.classes_today" :key="entry.id" class="relative">
              <span
                class="absolute top-2 -left-[1.62rem] size-2.5 rounded-full ring-4 ring-surface"
                :class="{ now: 'bg-brand', past: 'bg-line', later: 'bg-accent' }[status(entry.starts_at, entry.ends_at)]"
              />
              <div class="block-kind rounded-xl px-4 py-3" :class="[`kind-${entry.kind}`, status(entry.starts_at, entry.ends_at) === 'past' ? 'opacity-60' : '']">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="font-medium">{{ entry.title }}</p>
                  <UiBadge v-if="status(entry.starts_at, entry.ends_at) === 'now'" tone="brand">now</UiBadge>
                </div>
                <p class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                  <span class="inline-flex items-center gap-1"><Clock3 class="size-3.5" />{{ entry.starts_at }}–{{ entry.ends_at }}</span>
                  <span v-if="entry.location" class="inline-flex items-center gap-1"><MapPin class="size-3.5" />{{ entry.location }}</span>
                  <span v-if="entry.instructor">{{ entry.instructor }}</span>
                </p>
              </div>
            </li>
          </ol>
        </UiCard>

        <div class="grid gap-6 lg:grid-cols-2">
          <UiCard title="Due in the next 3 days" :subtitle="briefing.due_soon.length ? undefined : 'Nothing urgent'">
            <ul v-if="briefing.due_soon.length" class="-my-2 divide-y divide-line">
              <TodayTaskLine v-for="task in briefing.due_soon" :key="task.id" :task="task" @toggle="toggle" />
            </ul>
            <p v-else class="text-sm text-muted">Enjoy it. Upcoming work is on the <NuxtLink to="/tasks" class="text-brand hover:underline">Tasks</NuxtLink> page.</p>
          </UiCard>
          <UiCard title="Overdue" :subtitle="briefing.overdue.length ? 'Finish, or mark done if already handed in' : 'All caught up'">
            <ul v-if="briefing.overdue.length" class="-my-2 divide-y divide-line">
              <TodayTaskLine v-for="task in briefing.overdue" :key="task.id" :task="task" overdue @toggle="toggle" />
            </ul>
            <p v-else class="text-sm text-muted">No missed deadlines.</p>
          </UiCard>
        </div>

        <UiCard v-if="briefing.clashes.length" title="Timetable clashes ahead">
          <ul class="space-y-2">
            <li v-for="clash in briefing.clashes" :key="`${clash.first_id}-${clash.second_id}`" class="flex gap-2 text-sm">
              <TriangleAlert class="mt-0.5 size-4 shrink-0 text-warn" /> {{ clash.description }}
            </li>
          </ul>
        </UiCard>
      </div>

      <aside class="space-y-6">
        <div class="grid grid-cols-2 gap-3">
          <TodayStat :icon="Inbox" label="Unread mail" :value="briefing.unread_mail" to="/mail" />
          <TodayStat :icon="ShieldQuestion" label="Waiting for you" :value="briefing.pending_approvals" to="/assistant" hint="assistant proposals" />
          <TodayStat :icon="BookOpenText" label="Library documents" :value="briefing.library_documents" to="/library" />
          <TodayStat
            :icon="RefreshCw"
            label="Last sync"
            :value="briefing.last_sync_at ? relativeTime(briefing.last_sync_at) : 'never'"
            :hint="briefing.last_sync_at ? formatDateTime(briefing.last_sync_at) : undefined"
            to="/settings"
          />
        </div>
        <UiCard v-if="briefing.tips.length" title="Worth a look">
          <ul class="space-y-3">
            <li v-for="tip in briefing.tips" :key="tip" class="flex gap-2.5 text-sm">
              <Lightbulb class="mt-0.5 size-4 shrink-0 text-warn" /> {{ tip }}
            </li>
          </ul>
        </UiCard>
        <UiCard title="Next up">
          <div v-if="briefing.next_class" class="text-sm">
            <p class="font-medium">{{ briefing.next_class.title }}</p>
            <p class="mt-1 text-muted">{{ briefing.next_class.starts_at }} · {{ briefing.next_class.location ?? 'no room set' }}</p>
          </div>
          <p v-else class="text-sm text-muted">No more classes today.</p>
        </UiCard>
      </aside>
    </div>

    <div v-else-if="planner.loading.briefing" class="grid gap-6 xl:grid-cols-3">
      <div v-for="n in 3" :key="n" class="panel h-48 animate-pulse bg-surface-muted/40" />
    </div>

    <PlannerStudyPlanDialog v-model:open="planOpen" />
  </div>
</template>
