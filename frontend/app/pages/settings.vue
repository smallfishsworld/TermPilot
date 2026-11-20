<script setup lang="ts">
import { CircleAlert, CircleCheck, LogOut, RefreshCw, Rss } from '@lucide/vue'
import type { Term } from '~/types/api'
import { useCampusStore } from '~/stores/campus'
import { useSessionStore } from '~/stores/session'
import { useToasts } from '~/stores/toasts'
import { formatDateTime } from '~/utils/format'

useHead({ title: 'Settings · TermPilot' })

const session = useSessionStore()
const campus = useCampusStore()
const toasts = useToasts()
const term = ref<Term | null>(null)
const photo = ref<string | null>(null)
const interests = ref('')
const termStart = ref('')
const saving = ref(false)
const subscribeOpen = ref(false)

const SOURCE_LABEL: Record<string, string> = {
  profile: 'Profile and photo', grades: 'GPA and credits', timetable: 'Timetable', deadlines: 'Calendar deadlines', coursework: 'Coursework grades', materials: 'Course files',
}

const profileRows = computed(() => {
  const student = session.student
  if (!student) return []
  return [
    ['Student number', student.is_demo ? 'demo account' : String(student.id)],
    ['Department', student.department],
    ['Class', student.class_name],
    ['College', student.college],
    ['Dormitory', student.dormitory],
    ['Email', student.email],
    ['Phone', student.phone],
  ].filter(([, value]) => value) as [string, string][]
})

async function load() {
  try {
    const http = useHttp()
    const [termData, photoData] = await Promise.all([
      http.get<Term>('/api/me/term'),
      http.get<{ data_url: string | null }>('/api/me/photo'),
      campus.loadRuns(),
      session.loadProfile(),
    ])
    term.value = termData
    photo.value = photoData.data_url
    interests.value = session.student?.interests ?? ''
    termStart.value = session.student?.term_start ?? ''
  }
  catch (error) {
    toasts.failure(error)
  }
}

async function savePreferences() {
  saving.value = true
  try {
    await session.updatePreferences(termStart.value ? { interests: interests.value, term_start: termStart.value } : { interests: interests.value, clear_term_start: true })
    term.value = await useHttp().get<Term>('/api/me/term')
    toasts.success('Preferences saved.')
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    saving.value = false
  }
}

async function syncNow() {
  try {
    await campus.sync()
    toasts.success('Sync finished.')
  }
  catch (error) {
    toasts.failure(error)
  }
}

onMounted(load)
</script>

<template>
  <div>
    <AppPageHeading title="Settings" subtitle="Your profile, preferences and connections.">
      <UiButton variant="danger" @click="session.signOut()"><LogOut class="size-4" /> Sign out everywhere</UiButton>
    </AppPageHeading>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <UiCard title="Profile" subtitle="Imported from academic records; read-only.">
        <div class="flex items-center gap-4">
          <img v-if="photo" :src="photo" alt="" class="size-16 rounded-2xl object-cover">
          <div v-else class="grid size-16 place-items-center rounded-2xl bg-brand-soft text-xl font-semibold text-brand-strong">{{ session.student?.display_name?.[0] }}</div>
          <div>
            <p class="text-lg font-semibold">{{ session.student?.display_name }}</p>
            <p class="text-sm text-muted">{{ session.student?.pinyin_name }}</p>
          </div>
        </div>
        <dl class="mt-5 grid grid-cols-[8rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
          <template v-for="[label, value] in profileRows" :key="label">
            <dt class="text-muted">{{ label }}</dt>
            <dd class="truncate">{{ value }}</dd>
          </template>
        </dl>
      </UiCard>

      <UiCard title="Preferences">
        <form class="space-y-4" @submit.prevent="savePreferences">
          <div>
            <label class="label" for="interests">Interests and goals</label>
            <textarea id="interests" v-model="interests" class="input min-h-24" maxlength="2000" placeholder="e.g. aiming for a machine learning internship; prefers studying in the morning" />
            <p class="mt-1 text-xs text-muted">The assistant uses this as background when it plans and answers.</p>
          </div>
          <div>
            <label class="label" for="term-start">First day of teaching week 1</label>
            <input id="term-start" v-model="termStart" class="input w-56" type="date">
            <p class="mt-1 text-xs text-muted">
              <template v-if="term">Currently {{ term.label }}, starting {{ term.start }}{{ term.in_session ? `, week ${term.current_week}` : '' }}.</template>
              Leave empty to use the default calendar.
            </p>
          </div>
          <UiButton type="submit" variant="primary" :loading="saving">Save preferences</UiButton>
        </form>
      </UiCard>

      <UiCard title="Calendar subscription" subtitle="See classes and deadlines in Google, Apple or Outlook calendar.">
        <UiButton @click="subscribeOpen = true"><Rss class="size-4" /> Get my calendar link</UiButton>
      </UiCard>

      <UiCard title="Campus sync history">
        <template #actions>
          <UiButton size="sm" :loading="campus.syncing" @click="syncNow"><RefreshCw v-if="!campus.syncing" class="size-3.5" /> Sync now</UiButton>
        </template>
        <p v-if="!campus.runs.length" class="text-sm text-muted">No sync yet.</p>
        <ol class="space-y-4">
          <li v-for="run in campus.runs" :key="run.id">
            <p class="flex items-center gap-2 text-sm font-medium">
              {{ formatDateTime(run.started_at) }}
              <UiBadge :tone="run.outcome === 'ok' ? 'ok' : run.outcome === 'partial' ? 'warn' : 'danger'">{{ run.outcome }}</UiBadge>
            </p>
            <ul class="mt-1.5 space-y-1">
              <li v-for="step in run.steps" :key="step.source" class="flex items-start gap-2 text-xs">
                <CircleCheck v-if="step.ok" class="mt-0.5 size-3.5 shrink-0 text-ok" />
                <CircleAlert v-else class="mt-0.5 size-3.5 shrink-0 text-danger" />
                <span><b class="font-medium">{{ SOURCE_LABEL[step.source] ?? step.source }}</b> <span class="text-muted">{{ step.message }}</span></span>
              </li>
            </ul>
          </li>
        </ol>
      </UiCard>
    </div>

    <PlannerSubscribeDialog v-model:open="subscribeOpen" />
  </div>
</template>
