<script setup lang="ts">
import { Download, File, Folder, FolderOpen, Trash2, Upload } from '@lucide/vue'
import type { WorkspaceFile } from '~/types/api'
import { useFilesStore } from '~/stores/files'
import { useToasts } from '~/stores/toasts'
import { formatBytes, formatDateTime } from '~/utils/format'

const files = useFilesStore()
const toasts = useToasts()
const folder = ref('.')
const input = ref<HTMLInputElement | null>(null)

const items = computed(() => {
  const prefix = folder.value === '.' ? '' : `${folder.value}/`
  return files.workspace.files
    .filter(item => item.path.startsWith(prefix) && !item.path.slice(prefix.length).includes('/'))
    .sort((a, b) => Number(b.is_dir) - Number(a.is_dir) || a.path.localeCompare(b.path))
})
const crumbs = computed(() => (folder.value === '.' ? [] : folder.value.split('/')))
const usage = computed(() => (files.workspace.quota_bytes ? Math.round((files.workspace.usage_bytes / files.workspace.quota_bytes) * 100) : 0))

function name(item: WorkspaceFile) {
  return item.path.split('/').pop()
}

async function upload(list: FileList | null) {
  try {
    for (const file of list ?? []) await files.uploadToWorkspace(folder.value, file)
    toasts.success('Uploaded.')
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    if (input.value) input.value.value = ''
  }
}

async function makeFolder() {
  const title = prompt('Folder name')?.trim()
  if (!title) return
  folder.value = folder.value === '.' ? title : `${folder.value}/${title}`
}

async function remove(item: WorkspaceFile) {
  if (!confirm(`Move ${item.path} to the trash?`)) return
  await files.removeFromWorkspace(item.path).catch(toasts.failure)
}
</script>

<template>
  <div class="space-y-4">
    <p class="text-sm text-muted">
      A private folder on the server. The assistant can list and read these files and propose edits or batch renames, which you approve first.
    </p>
    <UiCard :padded="false">
      <div class="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3 text-sm">
        <button class="inline-flex items-center gap-1 font-medium hover:text-brand" @click="folder = '.'"><FolderOpen class="size-4" /> workspace</button>
        <template v-for="(crumb, index) in crumbs" :key="index">
          <span class="text-muted">/</span>
          <button class="hover:text-brand" @click="folder = crumbs.slice(0, index + 1).join('/')">{{ crumb }}</button>
        </template>
        <div class="ml-auto flex gap-2">
          <UiButton size="sm" variant="ghost" @click="makeFolder"><Folder class="size-3.5" /> New folder</UiButton>
          <UiButton size="sm" @click="input?.click()"><Upload class="size-3.5" /> Upload</UiButton>
          <input ref="input" type="file" class="hidden" multiple @change="upload(($event.target as HTMLInputElement).files)">
        </div>
      </div>
      <UiEmpty v-if="!items.length" :icon="FolderOpen" title="This folder is empty" text="Upload files here, for example lecture notes the assistant can read or tidy up." />
      <ul v-else class="divide-y divide-line">
        <li v-for="item in items" :key="item.path" class="flex items-center gap-3 px-4 py-2.5 text-sm">
          <component :is="item.is_dir ? Folder : File" class="size-4 shrink-0" :class="item.is_dir ? 'text-brand' : 'text-muted'" />
          <button v-if="item.is_dir" class="min-w-0 flex-1 truncate text-left font-medium hover:text-brand" @click="folder = item.path">{{ name(item) }}</button>
          <span v-else class="min-w-0 flex-1 truncate">{{ name(item) }}</span>
          <span class="hidden w-24 text-right text-xs text-muted sm:block">{{ item.is_dir ? '' : formatBytes(item.size) }}</span>
          <span class="hidden w-40 text-right text-xs text-muted md:block">{{ formatDateTime(item.modified) }}</span>
          <UiButton v-if="!item.is_dir" size="sm" variant="ghost" :aria-label="`Download ${name(item)}`" @click="files.download(item.path).catch(toasts.failure)"><Download class="size-3.5" /></UiButton>
          <UiButton size="sm" variant="ghost" :aria-label="`Delete ${name(item)}`" @click="remove(item)"><Trash2 class="size-3.5" /></UiButton>
        </li>
      </ul>
      <div class="border-t border-line px-4 py-2.5">
        <div class="h-1.5 overflow-hidden rounded-full bg-surface-muted"><div class="h-full rounded-full bg-brand" :style="{ width: `${usage}%` }" /></div>
        <p class="mt-1 text-xs text-muted">{{ formatBytes(files.workspace.usage_bytes) }} of {{ formatBytes(files.workspace.quota_bytes) }} used</p>
      </div>
    </UiCard>
  </div>
</template>
