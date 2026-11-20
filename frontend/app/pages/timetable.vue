<script setup lang="ts">
import { CalendarPlus, CalendarRange, ChevronLeft, ChevronRight, Plus, Rss, TriangleAlert } from '@lucide/vue'
import type { Entry } from '~/types/api'
import { usePlannerStore } from '~/stores/planner'
import { useToasts } from '~/stores/toasts'
import { WEEKDAY_NAMES, dateOfWeek, describeWeeks, formatDay, occursInWeek } from '~/utils/calendar'
import { formatShortDate } from '~/utils/format'

useHead({ title: 'Timetable · TermPilot' })

const planner = usePlannerStore()
const toasts = useToasts()
const week = ref(1)
const editing = ref<Entry | null>(null)
const preset = ref<{ weekday: number, starts_at: string } | null>(null)
const dialogs = reactive({ entry: false, plan: false, subscribe: false })
const view = ref<'week' | 'list'>('week')

const term = computed(() => planner.term)
// Highlight the campus date from the API; the browser may run in another time zone.
const today = computed(() => term.value?.today ?? formatDay(new Date()))
const monday = computed(() => (term.value ? dateOfWeek(term.value.start, week.value, 1) : today.value))
const visible = computed(() => planner.entries.filter(entry => occursInWeek(entry.weeks, week.value)))
const weekClashes = computed(() => planner.clashes.filter(clash => clash.weeks.includes(week.value)))
const clashIds = computed(() => new Set(weekClashes.value.flatMap(clash => [clash.first_id, clash.second_id])))
const byDay = computed(() => WEEKDAY_NAMES.map((name, index) => ({ name, entries: visible.value.filter(entry => entry.weekday === index + 1) })))

async function load() {
  try {
    await planner.loadTimetable()
    if (term.value) week.value = Math.min(Math.max(term.value.current_week, 1), term.value.weeks)
  }
  catch (error) {
    toasts.failure(error)
  }
}

function openEntry(entry: Entry) {
  editing.value = entry
  preset.value = null
  dialogs.entry = true
}

function createEntry(weekday = 1, startsAt = '14:00') {
  editing.value = null
  preset.value = { weekday, starts_at: startsAt }
  dialogs.entry = true
}

onMounted(load)
</script>

<template>
  <div>
    <AppPageHeading title="Timetable" :subtitle="term ? `${term.label} · ${term.start} to ${term.end}` : 'Loading…'">
      <UiButton @click="dialogs.subscribe = true"><Rss class="size-4" /> Subscribe</UiButton>
      <UiButton @click="dialogs.plan = true"><CalendarPlus class="size-4" /> Plan study time</UiButton>
      <UiButton variant="primary" @click="createEntry()"><Plus class="size-4" /> Add entry</UiButton>
    </AppPageHeading>

    <UiCard :padded="false">
      <div class="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
        <div class="flex items-center gap-1">
          <UiButton variant="ghost" size="sm" aria-label="Previous week" :disabled="week <= 1" @click="week--"><ChevronLeft class="size-4" /></UiButton>
          <p class="min-w-40 text-center text-sm font-semibold">
            Week {{ week }}<span v-if="term" class="font-normal text-muted"> · {{ formatShortDate(monday) }} – {{ formatShortDate(dateOfWeek(term.start, week, 7)) }}</span>
          </p>
          <UiButton variant="ghost" size="sm" aria-label="Next week" :disabled="!term || week >= term.weeks" @click="week++"><ChevronRight class="size-4" /></UiButton>
        </div>
        <UiButton v-if="term && term.in_session && week !== term.current_week" size="sm" @click="week = term.current_week">This week</UiButton>
        <div class="ml-auto"><UiSegmented v-model="view" :options="[{ value: 'week', label: 'Week' }, { value: 'list', label: 'List' }]" /></div>
      </div>

      <div v-if="weekClashes.length" class="flex gap-2 border-b border-line bg-warn-soft/60 px-4 py-2.5 text-sm text-warn">
        <TriangleAlert class="mt-0.5 size-4 shrink-0" />
        <div>
          <p v-for="clash in weekClashes" :key="`${clash.first_id}-${clash.second_id}`">{{ clash.description }}</p>
        </div>
      </div>

      <div class="p-4">
        <UiEmpty v-if="!planner.loading.timetable && !planner.entries.length" :icon="CalendarRange" title="Your timetable is empty" text="Sync with the campus systems to import your courses, or add your own entries.">
          <UiButton variant="primary" @click="createEntry()">Add an entry</UiButton>
        </UiEmpty>
        <PlannerWeekGrid v-else-if="view === 'week'" :entries="visible" :monday="monday" :today="today" :clash-ids="clashIds" @open="openEntry" @create="createEntry" />
        <div v-else class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <div v-for="day in byDay" :key="day.name">
            <p class="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">{{ day.name }}</p>
            <p v-if="!day.entries.length" class="text-sm text-muted/70">Free</p>
            <button
              v-for="entry in day.entries"
              :key="entry.id"
              class="block-kind mb-2 w-full rounded-lg px-3 py-2 text-left text-sm"
              :class="`kind-${entry.kind}`"
              @click="openEntry(entry)"
            >
              <p class="font-medium">{{ entry.title }}</p>
              <p class="text-xs text-muted">{{ entry.starts_at }}–{{ entry.ends_at }}{{ entry.location ? ` · ${entry.location}` : '' }} · weeks {{ describeWeeks(entry.weeks) }}</p>
            </button>
          </div>
        </div>
      </div>

      <div class="flex flex-wrap gap-3 border-t border-line px-4 py-3 text-xs text-muted">
        <span v-for="kind in ['course', 'study', 'activity', 'meeting', 'other']" :key="kind" class="inline-flex items-center gap-1.5" :class="`kind-${kind}`">
          <span class="block-kind size-3 rounded-sm" /> {{ kind }}
        </span>
        <span class="ml-auto">Click an empty slot to add an entry there.</span>
      </div>
    </UiCard>

    <PlannerEntryDialog v-model:open="dialogs.entry" :entry="editing" :preset="preset" />
    <PlannerStudyPlanDialog v-model:open="dialogs.plan" />
    <PlannerSubscribeDialog v-model:open="dialogs.subscribe" />
  </div>
</template>
