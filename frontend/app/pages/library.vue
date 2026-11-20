<script setup lang="ts">
import { useFilesStore } from '~/stores/files'
import { useToasts } from '~/stores/toasts'

useHead({ title: 'Library · TermPilot' })

const files = useFilesStore()
const toasts = useToasts()
const tab = ref<'documents' | 'workspace'>('documents')

watch(tab, (value) => {
  const load = value === 'documents' ? files.loadLibrary() : files.loadWorkspace()
  load.catch(toasts.failure)
}, { immediate: true })
</script>

<template>
  <div>
    <AppPageHeading title="Library" subtitle="Your own sources for grounded answers, and a private folder for file tasks.">
      <UiSegmented v-model="tab" :options="[{ value: 'documents', label: 'Documents' }, { value: 'workspace', label: 'Workspace' }]" />
    </AppPageHeading>
    <LibraryDocuments v-if="tab === 'documents'" />
    <LibraryWorkspace v-else />
  </div>
</template>
