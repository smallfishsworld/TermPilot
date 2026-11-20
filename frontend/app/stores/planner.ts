import { defineStore } from 'pinia'
import type { Briefing, Clash, Entry, EntryInput, StudyBlock, Task, TaskInput, Term, Timetable } from '~/types/api'

// Timetable, tasks and the Today briefing share one store because changes to
// one (a finished task, a new study block) affect the others.
export const usePlannerStore = defineStore('planner', () => {
  const term = ref<Term | null>(null)
  const entries = ref<Entry[]>([])
  const clashes = ref<Clash[]>([])
  const tasks = ref<Task[]>([])
  const briefing = ref<Briefing | null>(null)
  const loading = reactive({ timetable: false, tasks: false, briefing: false })

  const openTasks = computed(() => tasks.value.filter(task => !task.done))

  async function loadBriefing() {
    loading.briefing = true
    try {
      briefing.value = await useHttp().get<Briefing>('/api/briefing')
    }
    finally {
      loading.briefing = false
    }
  }

  async function loadTimetable() {
    loading.timetable = true
    try {
      const data = await useHttp().get<Timetable>('/api/timetable')
      term.value = data.term
      entries.value = data.entries
      clashes.value = data.clashes
    }
    finally {
      loading.timetable = false
    }
  }

  async function saveEntry(input: EntryInput, id?: number) {
    const http = useHttp()
    if (id) await http.patch<Entry>(`/api/timetable/${id}`, input)
    else await http.post<Entry>('/api/timetable', input)
    await loadTimetable()
  }

  async function deleteEntry(id: number) {
    await useHttp().del(`/api/timetable/${id}`)
    await loadTimetable()
  }

  async function loadTasks() {
    loading.tasks = true
    try {
      tasks.value = await useHttp().get<Task[]>('/api/tasks', { query: { status: 'all' } })
    }
    finally {
      loading.tasks = false
    }
  }

  async function saveTask(input: Partial<TaskInput> & { done?: boolean }, id?: number) {
    const http = useHttp()
    const saved = id ? await http.patch<Task>(`/api/tasks/${id}`, input) : await http.post<Task>('/api/tasks', input)
    const index = tasks.value.findIndex(task => task.id === saved.id)
    if (index === -1) tasks.value = [...tasks.value, saved]
    else tasks.value.splice(index, 1, saved)
    return saved
  }

  async function toggleDone(task: Task) {
    const saved = await saveTask({ done: !task.done }, task.id)
    if (briefing.value) {
      briefing.value.due_soon = briefing.value.due_soon.map(item => (item.id === saved.id ? saved : item))
      briefing.value.overdue = briefing.value.overdue.filter(item => item.id !== saved.id || !saved.done)
    }
    return saved
  }

  async function deleteTask(id: number) {
    await useHttp().del(`/api/tasks/${id}`)
    tasks.value = tasks.value.filter(task => task.id !== id)
  }

  async function suggestStudy(options: { days: number, block_minutes: number, day_start?: string, day_end?: string }) {
    return useHttp().post<StudyBlock[]>('/api/planner/suggestions', options)
  }

  async function acceptStudy(blocks: StudyBlock[]) {
    const created = await useHttp().post<Entry[]>('/api/planner/accept', {
      blocks: blocks.map(({ task_id, day, starts_at, ends_at }) => ({ task_id, day, starts_at, ends_at })),
    })
    await loadTimetable()
    return created
  }

  async function calendarLink() {
    return useHttp().get<{ url: string, expires_in_days: number }>('/api/calendar/link')
  }

  return {
    term, entries, clashes, tasks, briefing, loading, openTasks,
    loadBriefing, loadTimetable, saveEntry, deleteEntry, loadTasks, saveTask, toggleDone, deleteTask,
    suggestStudy, acceptStudy, calendarLink,
  }
})
