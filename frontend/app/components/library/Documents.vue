<script setup lang="ts">
import { FileText, LibraryBig, Trash2, Upload, WandSparkles } from '@lucide/vue'
import type { LibraryDocument } from '~/types/api'
import { useFilesStore } from '~/stores/files'
import { useToasts } from '~/stores/toasts'
import { formatBytes, formatDateTime } from '~/utils/format'

const files = useFilesStore()
const toasts = useToasts()
const input = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const studying = ref<LibraryDocument | null>(null)
const aidOpen = ref(false)

const STATUS_TONE = { ready: 'ok', processing: 'brand', empty: 'warn', failed: 'danger' } as const

async function upload(list: FileList | File[] | null) {
  const chosen = [...(list ?? [])]
  if (!chosen.length) return
  try {
    const report = await files.uploadDocuments(chosen)
    if (report.uploaded.length) toasts.success(`Indexed ${report.uploaded.length} document(s).`)
    for (const failure of report.failed) toasts.failure(new Error(`${failure.filename}: ${failure.reason}`))
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    if (input.value) input.value.value = ''
  }
}

function onDrop(event: DragEvent) {
  dragging.value = false
  upload(event.dataTransfer?.files ?? null)
}

async function remove(document: LibraryDocument) {
  if (!confirm(`Remove ${document.filename} from your library?`)) return
  await files.deleteDocument(document.id).catch(toasts.failure)
}

function study(document: LibraryDocument) {
  studying.value = document
  aidOpen.value = true
}
</script>

<template>
  <div class="space-y-4">
    <div v-if="!files.library.available" class="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
      {{ files.library.reason ?? 'The document library is not available.' }}
    </div>

    <label
      class="panel flex cursor-pointer flex-col items-center justify-center gap-2 border-2 border-dashed px-6 py-8 text-center transition"
      :class="[dragging ? 'border-brand bg-brand-soft/40' : 'hover:border-brand/50', files.library.available ? '' : 'pointer-events-none opacity-60']"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <Upload class="size-6 text-brand" />
      <p class="text-sm font-medium">{{ files.uploading ? 'Reading and indexing…' : 'Drop lecture notes, slides or handbooks here' }}</p>
      <p class="text-xs text-muted">PDF, Word, PowerPoint, Excel, Markdown, HTML or text · scanned PDFs are read with OCR</p>
      <input ref="input" type="file" class="hidden" multiple :disabled="!files.library.available || files.uploading" @change="upload(($event.target as HTMLInputElement).files)">
    </label>

    <UiCard :padded="false">
      <UiEmpty v-if="!files.library.documents.length" :icon="LibraryBig" title="No documents yet" text="Documents you add here can be searched by the assistant and turned into study aids." />
      <ul v-else class="divide-y divide-line">
        <li v-for="document in files.library.documents" :key="document.id" class="flex items-center gap-3 px-4 py-3">
          <FileText class="size-5 shrink-0 text-muted" />
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium">{{ document.filename }}</p>
            <p class="text-xs text-muted">
              {{ formatBytes(document.size_bytes) }} · {{ document.chunks }} passages · added {{ formatDateTime(document.created_at) }}
              <span v-if="document.error" class="text-danger"> · {{ document.error }}</span>
            </p>
          </div>
          <UiBadge :tone="STATUS_TONE[document.status]">{{ document.status }}</UiBadge>
          <UiButton size="sm" :disabled="document.status !== 'ready'" @click="study(document)"><WandSparkles class="size-3.5" /> Study aid</UiButton>
          <UiButton size="sm" variant="ghost" :aria-label="`Remove ${document.filename}`" @click="remove(document)"><Trash2 class="size-3.5" /></UiButton>
        </li>
      </ul>
    </UiCard>

    <LibraryStudyAidDialog v-model:open="aidOpen" :document="studying" />
  </div>
</template>
