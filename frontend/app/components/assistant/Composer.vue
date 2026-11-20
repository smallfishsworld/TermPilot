<script setup lang="ts">
import { ArrowUp, Paperclip, Square, X } from '@lucide/vue'
import type { AskMode } from '~/types/api'
import { useAssistantStore } from '~/stores/assistant'
import { useSessionStore } from '~/stores/session'
import { useToasts } from '~/stores/toasts'

const emit = defineEmits<{ send: [question: string, mode: AskMode, deepThink: boolean] }>()
const draft = defineModel<string>({ default: '' })
const assistant = useAssistantStore()
const session = useSessionStore()
const toasts = useToasts()
const mode = ref<AskMode>('agent')
const deepThink = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const textarea = ref<HTMLTextAreaElement | null>(null)
const attaching = ref(false)

const modes = computed(() => [
  { value: 'agent' as const, label: 'Agent', hint: 'Uses your timetable, tasks, mail and files; asks before changing anything' },
  { value: 'ask' as const, label: 'Ask', hint: 'Answers from your documents and attachments' },
  ...(session.features?.web_search ? [{ value: 'research' as const, label: 'Research', hint: 'Adds a web search' }] : []),
])

function resize() {
  const element = textarea.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 220)}px`
}

watch(draft, () => nextTick(resize))

function submit() {
  if (!draft.value.trim() || assistant.busy) return
  emit('send', draft.value, mode.value, deepThink.value)
  draft.value = ''
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}

async function onFiles(event: Event) {
  const files = [...((event.target as HTMLInputElement).files ?? [])]
  attaching.value = true
  try {
    for (const file of files) await assistant.attach(file)
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    attaching.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

defineExpose({ focus: () => textarea.value?.focus() })
</script>

<template>
  <div class="panel p-3 shadow-md">
    <div v-if="assistant.attachments.length" class="mb-2 flex flex-wrap gap-2">
      <span v-for="file in assistant.attachments" :key="file.id" class="chip">
        <Paperclip class="size-3" /> {{ file.filename }}<span v-if="file.truncated" title="Only the beginning is used">*</span>
        <button class="hover:text-danger" :aria-label="`Remove ${file.filename}`" @click="assistant.detach(file.id)"><X class="size-3" /></button>
      </span>
    </div>
    <textarea
      ref="textarea"
      v-model="draft"
      rows="1"
      class="max-h-56 w-full resize-none bg-transparent px-1 py-1 text-sm outline-none placeholder:text-muted/70"
      placeholder="Ask about your week, plan study time, draft an email…"
      @keydown="onKeydown"
    />
    <div class="mt-2 flex flex-wrap items-center gap-3">
      <UiSegmented v-model="mode" :options="modes" />
      <UiToggle v-model="deepThink" label="Deep think" />
      <input ref="fileInput" type="file" class="hidden" multiple accept=".pdf,.docx,.pptx,.txt,.md,.csv,.json,.py,.java,.c,.cpp,.js,.ts,.html,.tex" @change="onFiles">
      <UiButton variant="ghost" size="sm" :loading="attaching" title="Attach a file to this conversation" @click="fileInput?.click()">
        <Paperclip v-if="!attaching" class="size-4" />
      </UiButton>
      <div class="ml-auto">
        <UiButton v-if="assistant.busy" size="sm" @click="assistant.stop()"><Square class="size-3.5" /> Stop</UiButton>
        <UiButton v-else variant="primary" size="sm" :disabled="!draft.trim()" aria-label="Send" @click="submit"><ArrowUp class="size-4" /> Send</UiButton>
      </div>
    </div>
  </div>
</template>
