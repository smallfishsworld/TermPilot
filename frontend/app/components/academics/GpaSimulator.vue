<script setup lang="ts">
import { Plus, Trash2 } from '@lucide/vue'
import { LETTER_POINTS, pointsNeeded, projectGpa, type PlannedCourse } from '~/utils/gpa'

const props = defineProps<{ gpa: number | null, credits: number | null }>()

const courses = ref<PlannedCourse[]>([
  { name: 'This term course 1', credits: 3, points: 3.7 },
  { name: 'This term course 2', credits: 3, points: 3.3 },
])
const target = ref<number | null>(null)

const projected = computed(() => projectGpa(props.gpa, props.credits, courses.value))
const plannedCredits = computed(() => courses.value.reduce((sum, course) => sum + (course.credits > 0 ? course.credits : 0), 0))
const needed = computed(() =>
  target.value && props.gpa !== null && props.credits ? pointsNeeded(props.gpa, props.credits, plannedCredits.value, target.value) : null,
)

function add() {
  courses.value.push({ name: `Course ${courses.value.length + 1}`, credits: 3, points: 3.3 })
}
</script>

<template>
  <UiCard title="What-if GPA" subtitle="Credit-weighted average of grade points. Nothing here is saved.">
    <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_14rem]">
      <div>
        <div class="grid grid-cols-[minmax(0,1fr)_5rem_6.5rem_2rem] gap-2 text-xs font-medium text-muted uppercase">
          <span>Course</span><span>Credits</span><span>Grade</span><span />
        </div>
        <div v-for="(course, index) in courses" :key="index" class="mt-2 grid grid-cols-[minmax(0,1fr)_5rem_6.5rem_2rem] gap-2">
          <input v-model="course.name" class="input" :aria-label="`Course ${index + 1} name`">
          <input v-model.number="course.credits" class="input" type="number" min="0" max="20" step="0.5" :aria-label="`Course ${index + 1} credits`">
          <select v-model.number="course.points" class="input" :aria-label="`Course ${index + 1} grade`">
            <option v-for="(points, letter) in LETTER_POINTS" :key="letter" :value="points">{{ letter }} · {{ points.toFixed(1) }}</option>
          </select>
          <button class="grid place-items-center rounded-md text-muted hover:text-danger" :aria-label="`Remove course ${index + 1}`" @click="courses.splice(index, 1)"><Trash2 class="size-4" /></button>
        </div>
        <UiButton size="sm" variant="ghost" class="mt-3" @click="add"><Plus class="size-3.5" /> Add course</UiButton>
      </div>
      <div class="space-y-4 rounded-xl bg-surface-muted p-4">
        <div>
          <p class="text-xs text-muted">Current</p>
          <p class="text-2xl font-semibold tabular-nums">{{ gpa?.toFixed(2) ?? '—' }}</p>
          <p class="text-xs text-muted">{{ credits ?? 0 }} credits</p>
        </div>
        <div>
          <p class="text-xs text-muted">Projected</p>
          <p class="text-2xl font-semibold text-brand tabular-nums">{{ projected?.toFixed(2) ?? '—' }}</p>
          <p class="text-xs text-muted">with {{ plannedCredits }} more credits</p>
        </div>
        <div>
          <label class="label" for="gpa-target">Target GPA</label>
          <input id="gpa-target" v-model.number="target" class="input" type="number" min="0" max="4.3" step="0.01" placeholder="e.g. 3.80">
          <p v-if="needed !== null" class="mt-1 text-xs" :class="needed > 4 ? 'text-danger' : 'text-muted'">
            {{ needed > 4 ? 'Not reachable with these credits alone.' : `Needs an average of ${needed.toFixed(2)} in the planned courses.` }}
          </p>
        </div>
      </div>
    </div>
    <p v-if="gpa === null" class="mt-4 text-xs text-muted">Sync your grades to use your real GPA as the starting point.</p>
  </UiCard>
</template>
