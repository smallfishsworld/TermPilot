<script setup lang="ts">
import { CalendarPlus, Search } from '@lucide/vue'
import type { StudyBlock } from '~/types/api'
import { usePlannerStore } from '~/stores/planner'
import { useToasts } from '~/stores/toasts'
import { formatLongDate, formatMinutes } from '~/utils/format'
import { minutesOf } from '~/utils/calendar'

const open = defineModel<boolean>('open', { default: false })
const planner = usePlannerStore()
const toasts = useToasts()

const options = reactive({ days: 7, block_minutes: 90 })
const blocks = ref<StudyBlock[] | null>(null)
const chosen = ref<Set<string>>(new Set())
const searching = ref(false)
const saving = ref(false)

const key = (block: StudyBlock) => `${block.task_id}-${block.day}-${block.starts_at}`

const byDay = computed(() => {
  const groups = new Map<string, StudyBlock[]>()
  for (const block of blocks.value ?? []) groups.set(block.day, [...(groups.get(block.day) ?? []), block])
  return [...groups.entries()]
})

const chosenMinutes = computed(() =>
  (blocks.value ?? []).filter(block => chosen.value.has(key(block))).reduce((sum, block) => sum + minutesOf(block.ends_at) - minutesOf(block.starts_at), 0),
)

watch(open, (value) => {
  if (value) {
    blocks.value = null
    chosen.value = new Set()
  }
})

async function search() {
  searching.value = true
  try {
    blocks.value = await planner.suggestStudy({ ...options })
    chosen.value = new Set(blocks.value.map(key))
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    searching.value = false
  }
}

function toggle(block: StudyBlock) {
  const next = new Set(chosen.value)
  if (next.has(key(block))) next.delete(key(block))
  else next.add(key(block))
  chosen.value = next
}

async function accept() {
  const picks = (blocks.value ?? []).filter(block => chosen.value.has(key(block)))
  if (!picks.length) return
  saving.value = true
  try {
    await planner.acceptStudy(picks)
    toasts.success(`Added ${picks.length} study block(s) to your timetable.`)
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
  <UiDialog v-model:open="open" title="Plan study time" description="Finds free slots around your classes for open tasks, earliest deadline first." wide>
    <div class="flex flex-wrap items-end gap-3">
      <div>
        <label class="label" for="plan-days">Look ahead</label>
        <select id="plan-days" v-model.number="options.days" class="input w-36">
          <option v-for="days in [3, 5, 7, 10, 14]" :key="days" :value="days">{{ days }} days</option>
        </select>
      </div>
      <div>
        <label class="label" for="plan-block">Session length</label>
        <select id="plan-block" v-model.number="options.block_minutes" class="input w-36">
          <option v-for="minutes in [45, 60, 90, 120]" :key="minutes" :value="minutes">{{ formatMinutes(minutes) }}</option>
        </select>
      </div>
      <UiButton variant="primary" :loading="searching" @click="search">
        <Search v-if="!searching" class="size-4" /> Find free time
      </UiButton>
    </div>

    <p class="mt-3 text-xs text-muted">
      Tasks without an estimate count as 1.5 h (assignments 2.5 h, exams 4 h). Set an estimate on the Tasks page to plan more precisely.
    </p>

    <UiEmpty
      v-if="blocks && !blocks.length"
      class="mt-4"
      :icon="CalendarPlus"
      title="Nothing to plan"
      text="Either every open task already has study time booked, or there is no free time before its deadline."
    />

    <div v-for="[day, items] in byDay" :key="day" class="mt-5">
      <p class="text-xs font-semibold tracking-wide text-muted uppercase">{{ formatLongDate(day) }} · week {{ items[0]!.week }}</p>
      <ul class="mt-2 divide-y divide-line rounded-xl border border-line">
        <li v-for="block in items" :key="key(block)">
          <label class="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-surface-muted">
            <input type="checkbox" class="size-4 accent-[var(--tp-brand)]" :checked="chosen.has(key(block))" @change="toggle(block)">
            <span class="w-28 font-mono text-xs text-muted">{{ block.starts_at }}–{{ block.ends_at }}</span>
            <span class="flex-1 truncate text-sm">{{ block.task_title }}</span>
          </label>
        </li>
      </ul>
    </div>

    <template #footer>
      <span v-if="blocks?.length" class="mr-auto self-center text-xs text-muted">{{ chosen.size }} selected · {{ formatMinutes(chosenMinutes) }}</span>
      <UiButton @click="open = false">Close</UiButton>
      <UiButton variant="primary" :disabled="!chosen.size" :loading="saving" @click="accept">Add to timetable</UiButton>
    </template>
  </UiDialog>
</template>
