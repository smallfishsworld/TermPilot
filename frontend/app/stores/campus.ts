import { defineStore } from 'pinia'
import type { Academics, Material, SyncRun } from '~/types/api'

// Grades, credits, course files and the history of campus imports.
export const useCampusStore = defineStore('campus', () => {
  const academics = ref<Academics | null>(null)
  const materials = ref<Material[]>([])
  const runs = ref<SyncRun[]>([])
  const syncing = ref(false)

  const lastRun = computed(() => runs.value[0] ?? null)

  async function loadAcademics() {
    academics.value = await useHttp().get<Academics>('/api/academics')
  }

  async function loadMaterials() {
    materials.value = await useHttp().get<Material[]>('/api/academics/materials')
  }

  async function loadRuns() {
    runs.value = await useHttp().get<SyncRun[]>('/api/sync/runs')
  }

  async function sync(sources?: string[]): Promise<SyncRun> {
    syncing.value = true
    try {
      const run = await useHttp().post<SyncRun>('/api/sync', sources ? { sources } : {})
      runs.value = [run, ...runs.value.filter(item => item.id !== run.id)]
      return run
    }
    finally {
      syncing.value = false
    }
  }

  return { academics, materials, runs, syncing, lastRun, loadAcademics, loadMaterials, loadRuns, sync }
})
