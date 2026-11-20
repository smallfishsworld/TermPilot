<script setup lang="ts">
import { Trash2 } from '@lucide/vue'
import type { Priority, Task } from '~/types/api'
import { usePlannerStore } from '~/stores/planner'
import { useToasts } from '~/stores/toasts'
import { fromLocalInput, toLocalInput } from '~/utils/format'

const props = defineProps<{ task: Task | null, draft?: Partial<Task> | null }>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ saved: [task: Task] }>()
const planner = usePlannerStore()
const toasts = useToasts()

const form = reactive({ title: '', due: '', course: '', category: 'assignment', priority: 'normal' as Priority, effort: '', notes: '' })
const saving = ref(false)

function defaultDue() {
  const due = new Date(Date.now() + 2 * 86_400_000)
  due.setHours(23, 59, 0, 0)
  return toLocalInput(due.toISOString())
}

watch(open, (value) => {
  if (!value) return
  const source = props.task ?? props.draft ?? null
  Object.assign(form, {
    title: source?.title ?? '',
    due: source?.due_at ? toLocalInput(source.due_at) : defaultDue(),
    course: source?.course ?? '',
    category: source?.category ?? 'assignment',
    priority: source?.priority ?? 'normal',
    effort: source?.effort_minutes ? String(source.effort_minutes / 60) : '',
    notes: source?.notes ?? '',
  })
})

async function save() {
  saving.value = true
  try {
    const hours = Number.parseFloat(form.effort)
    const saved = await planner.saveTask({
      title: form.title.trim(),
      due_at: fromLocalInput(form.due),
      course: form.course.trim() || null,
      category: form.category || null,
      priority: form.priority,
      effort_minutes: Number.isFinite(hours) && hours > 0 ? Math.round(hours * 60) : null,
      notes: form.notes.trim() || null,
    }, props.task?.id)
    toasts.success(props.task ? 'Task updated.' : 'Task added.')
    emit('saved', saved)
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
  if (!props.task || !confirm(`Delete "${props.task.title}"?`)) return
  try {
    await planner.deleteTask(props.task.id)
    open.value = false
  }
  catch (error) {
    toasts.failure(error)
  }
}
</script>

<template>
  <UiDialog v-model:open="open" :title="task ? 'Edit task' : 'New task'">
    <form id="task-form" class="grid gap-4 sm:grid-cols-2" @submit.prevent="save">
      <div class="sm:col-span-2">
        <label class="label" for="task-title">Title</label>
        <input id="task-title" v-model="form.title" class="input" required maxlength="300">
      </div>
      <div>
        <label class="label" for="task-due">Due</label>
        <input id="task-due" v-model="form.due" type="datetime-local" class="input" required>
      </div>
      <div>
        <label class="label" for="task-course">Course</label>
        <input id="task-course" v-model="form.course" class="input" maxlength="200">
      </div>
      <div>
        <label class="label" for="task-category">Category</label>
        <select id="task-category" v-model="form.category" class="input">
          <option value="assignment">Assignment</option>
          <option value="exam">Exam</option>
          <option value="project">Project</option>
          <option value="admin">Admin</option>
          <option value="personal">Personal</option>
        </select>
      </div>
      <div>
        <label class="label" for="task-priority">Priority</label>
        <select id="task-priority" v-model="form.priority" class="input">
          <option value="low">Low</option>
          <option value="normal">Normal</option>
          <option value="high">High</option>
        </select>
      </div>
      <div class="sm:col-span-2">
        <label class="label" for="task-effort">Estimated effort (hours)</label>
        <input id="task-effort" v-model="form.effort" type="number" min="0.25" max="100" step="0.25" class="input" placeholder="Used by the study planner">
      </div>
      <div class="sm:col-span-2">
        <label class="label" for="task-notes">Notes</label>
        <textarea id="task-notes" v-model="form.notes" class="input min-h-20" maxlength="4000" />
      </div>
      <p v-if="task?.origin === 'lms'" class="text-xs text-muted sm:col-span-2">
        From the learning platform: the title and due date follow the platform on every sync. Your priority, effort and notes are kept.
      </p>
    </form>
    <template #footer>
      <UiButton v-if="task" variant="ghost" class="mr-auto text-danger" @click="remove"><Trash2 class="size-4" /> Delete</UiButton>
      <UiButton @click="open = false">Cancel</UiButton>
      <UiButton type="submit" form="task-form" variant="primary" :loading="saving">Save</UiButton>
    </template>
  </UiDialog>
</template>
