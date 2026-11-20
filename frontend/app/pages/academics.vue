<script setup lang="ts">
import { useEventListener } from '@vueuse/core'
import { Award, ExternalLink, FileDown, GraduationCap, Layers, Trophy } from '@lucide/vue'
import { useCampusStore } from '~/stores/campus'
import { useToasts } from '~/stores/toasts'
import { formatDateTime } from '~/utils/format'

useHead({ title: 'Academics · TermPilot' })

const campus = useCampusStore()
const toasts = useToasts()
const materialFilter = ref('')

const data = computed(() => campus.academics)
const categories = computed(() => {
  const entries = Object.entries(data.value?.credits_by_category ?? {}).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...entries.map(([, value]) => value))
  return entries.map(([name, value]) => ({ name, value, width: `${(value / max) * 100}%` }))
})
const materialsByCourse = computed(() => {
  const needle = materialFilter.value.trim().toLowerCase()
  const groups = new Map<string, typeof campus.materials>()
  for (const item of campus.materials) {
    if (needle && !`${item.course_title} ${item.title}`.toLowerCase().includes(needle)) continue
    groups.set(item.course_title, [...(groups.get(item.course_title) ?? []), item])
  }
  return [...groups.entries()]
})

function scoreTone(score: string) {
  const fraction = score.match(/^([\d.]+)\/([\d.]+)$/)
  const ratio = fraction ? Number(fraction[1]) / Number(fraction[2]) : /^A/.test(score) ? 0.95 : /^B/.test(score) ? 0.82 : /^C/.test(score) ? 0.7 : null
  if (ratio === null) return 'neutral'
  return ratio >= 0.9 ? 'ok' : ratio >= 0.75 ? 'brand' : ratio >= 0.6 ? 'warn' : 'danger'
}

onMounted(() => Promise.all([campus.loadAcademics(), campus.loadMaterials()]).catch(toasts.failure))
useEventListener(window, 'termpilot:synced', () => Promise.all([campus.loadAcademics(), campus.loadMaterials()]).catch(toasts.failure))
</script>

<template>
  <div>
    <AppPageHeading title="Academics" :subtitle="data?.credits_refreshed_at ? `Records updated ${formatDateTime(data.credits_refreshed_at)}` : 'Sync to import grades and credits'" />

    <div class="grid gap-4 sm:grid-cols-3">
      <div class="panel flex items-center gap-4 p-5">
        <div class="grid size-11 place-items-center rounded-xl bg-brand-soft text-brand-strong"><GraduationCap class="size-5" /></div>
        <div><p class="text-2xl font-semibold tabular-nums">{{ data?.gpa?.toFixed(2) ?? '—' }}</p><p class="text-xs text-muted">GPA</p></div>
      </div>
      <div class="panel flex items-center gap-4 p-5">
        <div class="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent"><Trophy class="size-5" /></div>
        <div><p class="text-2xl font-semibold tabular-nums">{{ data?.rank ?? '—' }}</p><p class="text-xs text-muted">Rank</p></div>
      </div>
      <div class="panel flex items-center gap-4 p-5">
        <div class="grid size-11 place-items-center rounded-xl bg-warn-soft text-warn"><Award class="size-5" /></div>
        <div><p class="text-2xl font-semibold tabular-nums">{{ data?.credits_total ?? '—' }}</p><p class="text-xs text-muted">Credits earned</p></div>
      </div>
    </div>

    <div class="mt-6 grid gap-6 xl:grid-cols-2">
      <UiCard title="Credits by category">
        <UiEmpty v-if="!categories.length" :icon="Layers" title="No credit data yet" />
        <ul v-else class="space-y-3">
          <li v-for="category in categories" :key="category.name">
            <div class="flex justify-between text-sm"><span>{{ category.name }}</span><span class="font-medium tabular-nums">{{ category.value }}</span></div>
            <div class="mt-1 h-2 overflow-hidden rounded-full bg-surface-muted"><div class="h-full rounded-full bg-brand" :style="{ width: category.width }" /></div>
          </li>
        </ul>
      </UiCard>

      <UiCard title="Coursework grades" subtitle="Graded items from the learning platform">
        <UiEmpty v-if="!data?.courses.length" :icon="Award" title="No graded items yet" />
        <div v-else class="space-y-4">
          <div v-for="course in data.courses" :key="course.course">
            <p class="text-sm font-medium">{{ course.course }}</p>
            <ul class="mt-1.5 divide-y divide-line rounded-lg border border-line">
              <li v-for="item in course.items" :key="item.item" class="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <span class="truncate">{{ item.item }}</span>
                <UiBadge :tone="scoreTone(item.score)">{{ item.score }}</UiBadge>
              </li>
            </ul>
          </div>
        </div>
      </UiCard>
    </div>

    <div class="mt-6"><AcademicsGpaSimulator :gpa="data?.gpa ?? null" :credits="data?.credits_total ?? null" /></div>

    <UiCard class="mt-6" title="Course files" subtitle="Links to materials posted on course pages">
      <template #actions><input v-model="materialFilter" class="input w-56" type="search" placeholder="Filter files"></template>
      <UiEmpty v-if="!materialsByCourse.length" :icon="FileDown" title="No course files listed" text="Files appear here after a sync." />
      <div v-else class="grid gap-5 md:grid-cols-2">
        <div v-for="[course, items] in materialsByCourse" :key="course">
          <p class="text-sm font-medium">{{ course }}</p>
          <ul class="mt-1.5 space-y-1">
            <li v-for="item in items" :key="item.id">
              <a :href="item.url" target="_blank" rel="noopener noreferrer" class="group flex items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-surface-muted">
                <FileDown class="size-4 shrink-0 text-muted" />
                <span class="min-w-0 flex-1 truncate">{{ item.title }}</span>
                <span v-if="item.section" class="hidden truncate text-xs text-muted sm:inline">{{ item.section }}</span>
                <ExternalLink class="size-3 text-muted opacity-0 group-hover:opacity-100" />
              </a>
            </li>
          </ul>
        </div>
      </div>
    </UiCard>
  </div>
</template>
