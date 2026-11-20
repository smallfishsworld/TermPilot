<script setup lang="ts">
import { Copy, WandSparkles } from '@lucide/vue'
import type { LibraryDocument } from '~/types/api'
import { useFilesStore } from '~/stores/files'
import { useToasts } from '~/stores/toasts'
import { renderAnswer } from '~/utils/markdown'

const props = defineProps<{ document: LibraryDocument | null }>()
const open = defineModel<boolean>('open', { default: false })
const files = useFilesStore()
const toasts = useToasts()
const kind = ref<'summary' | 'quiz' | 'flashcards'>('summary')
const text = ref('')
const running = ref(false)
let controller: AbortController | null = null

watch(open, (value) => {
  if (!value) controller?.abort()
  text.value = ''
})

async function generate() {
  if (!props.document) return
  controller?.abort()
  controller = new AbortController()
  text.value = ''
  running.value = true
  try {
    await files.studyAid(props.document.id, kind.value, (chunk) => { text.value += chunk }, controller.signal)
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    running.value = false
  }
}

async function copy() {
  await navigator.clipboard.writeText(text.value)
  toasts.success('Copied as Markdown.')
}
</script>

<template>
  <UiDialog v-model:open="open" :title="`Study aid: ${document?.filename ?? ''}`" description="Generated only from this document's text." wide>
    <div class="flex flex-wrap items-center gap-3">
      <UiSegmented v-model="kind" :options="[{ value: 'summary', label: 'Revision summary' }, { value: 'quiz', label: 'Practice quiz' }, { value: 'flashcards', label: 'Flashcards' }]" />
      <UiButton variant="primary" :loading="running" @click="generate"><WandSparkles v-if="!running" class="size-4" /> Generate</UiButton>
      <UiButton v-if="text && !running" variant="ghost" @click="copy"><Copy class="size-4" /> Copy</UiButton>
    </div>
    <!-- eslint-disable-next-line vue/no-v-html -- rendered with raw HTML disabled -->
    <div v-if="text" class="answer mt-5" v-html="renderAnswer(text)" />
    <p v-else-if="!running" class="mt-5 text-sm text-muted">Choose a format and press Generate.</p>
  </UiDialog>
</template>
