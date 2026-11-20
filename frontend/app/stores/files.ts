import { defineStore } from 'pinia'
import type { LibraryDocument, LibraryState, WorkspaceFile, WorkspaceListing } from '~/types/api'
import { readEventStream } from '~/utils/sse'

// The searchable document library and the private workspace folder.
export const useFilesStore = defineStore('files', () => {
  const library = ref<LibraryState>({ available: false, reason: null, documents: [] })
  const workspace = ref<WorkspaceListing>({ files: [], usage_bytes: 0, quota_bytes: 0 })
  const uploading = ref(false)

  async function loadLibrary() {
    library.value = await useHttp().get<LibraryState>('/api/library/documents')
  }

  async function uploadDocuments(files: File[]) {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    uploading.value = true
    try {
      const report = await useHttp().request<{ uploaded: LibraryDocument[], failed: { filename: string, reason: string }[] }>(
        'POST', '/api/library/documents', { form },
      )
      await loadLibrary()
      return report
    }
    finally {
      uploading.value = false
    }
  }

  async function deleteDocument(id: number) {
    await useHttp().del(`/api/library/documents/${id}`)
    library.value.documents = library.value.documents.filter(item => item.id !== id)
  }

  /** Stream a study aid; `onText` receives Markdown as it is written. */
  async function studyAid(id: number, kind: 'summary' | 'quiz' | 'flashcards', onText: (text: string) => void, signal?: AbortSignal) {
    const response = await useHttp().raw('POST', `/api/library/documents/${id}/study-aid`, { json: { kind }, signal })
    let failure: string | null = null
    await readEventStream(response, ({ event, data }) => {
      if (event === 'answer') onText(data.text)
      if (event === 'error') failure = data.message
    })
    if (failure) throw new Error(failure)
  }

  async function loadWorkspace(folder = '.') {
    workspace.value = await useHttp().get<WorkspaceListing>('/api/workspace/files', { query: { folder } })
  }

  async function uploadToWorkspace(folder: string, file: File, replace = false) {
    const form = new FormData()
    form.append('file', file)
    await useHttp().request<WorkspaceFile>('POST', '/api/workspace/files', { form, query: { folder, replace } })
    await loadWorkspace()
  }

  async function removeFromWorkspace(path: string) {
    await useHttp().del('/api/workspace/files', { query: { path } })
    await loadWorkspace()
  }

  async function download(path: string) {
    const response = await useHttp().raw('GET', '/api/workspace/download', { query: { path } })
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = path.split('/').pop() ?? 'file'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  return { library, workspace, uploading, loadLibrary, uploadDocuments, deleteDocument, studyAid, loadWorkspace, uploadToWorkspace, removeFromWorkspace, download }
})
