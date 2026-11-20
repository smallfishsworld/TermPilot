<script setup lang="ts">
import { Trash2 } from '@lucide/vue'
import type { Entry, EntryInput, EntryKind } from '~/types/api'
import { usePlannerStore } from '~/stores/planner'
import { useToasts } from '~/stores/toasts'
import { WEEKDAY_NAMES, describeWeeks, minutesOf, parseWeekList } from '~/utils/calendar'

const props = defineProps<{ entry: Entry | null, preset?: { weekday: number, starts_at: string } | null }>()
const open = defineModel<boolean>('open', { default: false })
const planner = usePlannerStore()
const toasts = useToasts()

const KINDS: { value: EntryKind, label: string }[] = [
  { value: 'course', label: 'Course' },
  { value: 'study', label: 'Study session' },
  { value: 'activity', label: 'Activity' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'other', label: 'Other' },
]

const form = reactive({ title: '', kind: 'activity' as EntryKind, weekday: 1, starts_at: '14:00', ends_at: '15:30', weeks: '', location: '', instructor: '', notes: '' })
const saving = ref(false)
const problem = ref<string | null>(null)

watch(open, (value) => {
  if (!value) return
  problem.value = null
  const entry = props.entry
  Object.assign(form, entry
    ? { title: entry.title, kind: entry.kind, weekday: entry.weekday, starts_at: entry.starts_at, ends_at: entry.ends_at, weeks: entry.weeks.length ? describeWeeks(entry.weeks) : '', location: entry.location ?? '', instructor: entry.instructor ?? '', notes: entry.notes ?? '' }
    : { title: '', kind: 'activity', weekday: props.preset?.weekday ?? 1, starts_at: props.preset?.starts_at ?? '14:00', ends_at: addMinutes(props.preset?.starts_at ?? '14:00', 90), weeks: '', location: '', instructor: '', notes: '' })
})

function addMinutes(time: string, minutes: number) {
  const total = Math.min(minutesOf(time) + minutes, 23 * 60 + 59)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

const weekPreview = computed(() => {
  const parsed = parseWeekList(form.weeks)
  return form.weeks.trim() && !parsed.length ? 'Could not read these weeks' : describeWeeks(parsed)
})

async function save() {
  if (minutesOf(form.ends_at) <= minutesOf(form.starts_at)) {
    problem.value = 'The end time must be after the start time.'
    return
  }
  const input: EntryInput = {
    title: form.title.trim(),
    kind: form.kind,
    weekday: form.weekday,
    starts_at: form.starts_at,
    ends_at: form.ends_at,
    weeks: parseWeekList(form.weeks),
    location: form.location.trim() || null,
    instructor: form.instructor.trim() || null,
    notes: form.notes.trim() || null,
  }
  saving.value = true
  try {
    await planner.saveEntry(input, props.entry?.id)
    toasts.success(props.entry ? 'Entry updated.' : 'Entry added.')
    open.value = false
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    saving.value = false
  }
}

async function remove() {
  if (!props.entry || !confirm(`Remove "${props.entry.title}" from the timetable?`)) return
  try {
    await planner.deleteEntry(props.entry.id)
    toasts.success('Entry removed.')
    open.value = false
  }
  catch (error) {
    toasts.failure(error)
  }
}
</script>

<template>
  <UiDialog v-model:open="open" :title="entry ? 'Edit entry' : 'New entry'">
    <form id="entry-form" class="grid gap-4 sm:grid-cols-2" @submit.prevent="save">
      <div class="sm:col-span-2">
        <label class="label" for="entry-title">Title</label>
        <input id="entry-title" v-model="form.title" class="input" required maxlength="200" placeholder="e.g. Badminton club">
      </div>
      <div>
        <label class="label" for="entry-kind">Kind</label>
        <select id="entry-kind" v-model="form.kind" class="input">
          <option v-for="kind in KINDS" :key="kind.value" :value="kind.value">{{ kind.label }}</option>
        </select>
      </div>
      <div>
        <label class="label" for="entry-day">Day</label>
        <select id="entry-day" v-model.number="form.weekday" class="input">
          <option v-for="(name, index) in WEEKDAY_NAMES" :key="name" :value="index + 1">{{ name }}</option>
        </select>
      </div>
      <div>
        <label class="label" for="entry-start">Starts</label>
        <input id="entry-start" v-model="form.starts_at" type="time" class="input" required>
      </div>
      <div>
        <label class="label" for="entry-end">Ends</label>
        <input id="entry-end" v-model="form.ends_at" type="time" class="input" required>
      </div>
      <div class="sm:col-span-2">
        <label class="label" for="entry-weeks">Teaching weeks</label>
        <input id="entry-weeks" v-model="form.weeks" class="input" placeholder="Leave empty for every week, or e.g. 1-8, 10, 12-16">
        <p class="mt-1 text-xs text-muted">{{ weekPreview }}</p>
      </div>
      <div>
        <label class="label" for="entry-location">Location</label>
        <input id="entry-location" v-model="form.location" class="input" maxlength="160">
      </div>
      <div>
        <label class="label" for="entry-instructor">With</label>
        <input id="entry-instructor" v-model="form.instructor" class="input" maxlength="160" placeholder="Instructor, coach, team…">
      </div>
      <div class="sm:col-span-2">
        <label class="label" for="entry-notes">Notes</label>
        <textarea id="entry-notes" v-model="form.notes" class="input min-h-20" maxlength="2000" />
      </div>
      <p v-if="entry?.origin === 'records'" class="text-xs text-muted sm:col-span-2">
        Imported from academic records. Once you edit it, it becomes your own entry and the next sync imports the official version again.
      </p>
      <p v-if="problem" class="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger sm:col-span-2">{{ problem }}</p>
    </form>
    <template #footer>
      <UiButton v-if="entry" variant="ghost" class="mr-auto text-danger" @click="remove"><Trash2 class="size-4" /> Delete</UiButton>
      <UiButton @click="open = false">Cancel</UiButton>
      <UiButton type="submit" form="entry-form" variant="primary" :loading="saving">Save</UiButton>
    </template>
  </UiDialog>
</template>
