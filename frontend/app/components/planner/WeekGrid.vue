<script setup lang="ts">
import type { Entry } from '~/types/api'
import { WEEKDAY_SHORT, addDays, layoutLanes, minutesOf } from '~/utils/calendar'

const props = defineProps<{ entries: Entry[], monday: string, today: string, clashIds: Set<number> }>()
const emit = defineEmits<{ open: [entry: Entry], create: [weekday: number, startsAt: string] }>()

const HOUR_HEIGHT = 52
const days = computed(() => WEEKDAY_SHORT.map((label, index) => ({ label, weekday: index + 1, date: addDays(props.monday, index) })))

// Show 08:00-22:00, stretched when an entry starts earlier or ends later.
const range = computed(() => {
  let first = 8 * 60
  let last = 22 * 60
  for (const entry of props.entries) {
    first = Math.min(first, Math.floor(minutesOf(entry.starts_at) / 60) * 60)
    last = Math.max(last, Math.ceil(minutesOf(entry.ends_at) / 60) * 60)
  }
  return { first, last }
})
const hours = computed(() => Array.from({ length: (range.value.last - range.value.first) / 60 }, (_, i) => range.value.first / 60 + i))
const height = computed(() => ((range.value.last - range.value.first) / 60) * HOUR_HEIGHT)

const placedByDay = computed(() =>
  days.value.map(day => layoutLanes(props.entries.filter(entry => entry.weekday === day.weekday))),
)

function style(start: string, end: string, lane: number, lanes: number) {
  const top = ((minutesOf(start) - range.value.first) / 60) * HOUR_HEIGHT
  const blockHeight = Math.max(((minutesOf(end) - minutesOf(start)) / 60) * HOUR_HEIGHT - 2, 18)
  return { top: `${top}px`, height: `${blockHeight}px`, left: `calc(${(lane / lanes) * 100}% + 2px)`, width: `calc(${100 / lanes}% - 4px)` }
}

function createAt(weekday: number, event: MouseEvent) {
  const offset = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const minutes = range.value.first + Math.floor(((event.clientY - offset.top) / HOUR_HEIGHT) * 2) * 30
  emit('create', weekday, `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${minutes % 60 ? '30' : '00'}`)
}
</script>

<template>
  <div class="overflow-x-auto">
    <div class="grid min-w-[760px] grid-cols-[3.25rem_repeat(7,minmax(0,1fr))]">
      <div />
      <div v-for="day in days" :key="day.date" class="border-b border-line px-2 pb-2 text-center">
        <p class="text-xs font-medium tracking-wide text-muted uppercase">{{ day.label }}</p>
        <p class="mt-0.5 text-sm font-semibold tabular-nums" :class="day.date === today ? 'mx-auto w-fit rounded-full bg-brand px-2 text-white dark:text-page' : ''">
          {{ Number(day.date.slice(8)) }}
        </p>
      </div>

      <div class="relative" :style="{ height: `${height}px` }">
        <span v-for="hour in hours" :key="hour" class="absolute right-2 -translate-y-1/2 text-[0.68rem] text-muted tabular-nums" :style="{ top: `${(hour - hours[0]!) * HOUR_HEIGHT}px` }">
          {{ String(hour).padStart(2, '0') }}:00
        </span>
      </div>
      <div
        v-for="(day, index) in days"
        :key="day.date"
        class="relative cursor-copy border-l border-line"
        :class="day.date === today ? 'bg-brand-soft/25' : ''"
        :style="{ height: `${height}px`, backgroundImage: `repeating-linear-gradient(to bottom, var(--tp-line) 0 1px, transparent 1px ${HOUR_HEIGHT}px)` }"
        @click.self="createAt(day.weekday, $event)"
      >
        <button
          v-for="placed in placedByDay[index]"
          :key="placed.item.id"
          class="block-kind absolute overflow-hidden rounded-md px-1.5 py-1 text-left text-xs shadow-sm transition hover:z-10 hover:shadow-md"
          :class="[`kind-${placed.item.kind}`, clashIds.has(placed.item.id) ? 'ring-2 ring-warn' : '']"
          :style="style(placed.item.starts_at, placed.item.ends_at, placed.lane, placed.lanes)"
          :title="`${placed.item.title} · ${placed.item.starts_at}-${placed.item.ends_at}${placed.item.location ? ` · ${placed.item.location}` : ''}`"
          @click="emit('open', placed.item)"
        >
          <p class="truncate font-semibold text-kind">{{ placed.item.title }}</p>
          <p class="truncate text-[0.68rem] text-muted">{{ placed.item.starts_at }}–{{ placed.item.ends_at }}</p>
          <p v-if="placed.item.location" class="truncate text-[0.68rem] text-muted">{{ placed.item.location }}</p>
        </button>
      </div>
    </div>
  </div>
</template>
