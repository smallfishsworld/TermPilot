<script setup lang="ts">
import { ListPlus, MailOpen, Reply } from '@lucide/vue'
import type { MailDetail } from '~/types/api'
import { formatDateTime } from '~/utils/format'

const props = defineProps<{ message: MailDetail | null, canExtract: boolean }>()
defineEmits<{ reply: [message: MailDetail], extract: [message: MailDetail] }>()

// HTML mail is shown in a sandbox without scripts, and remote images are
// blocked so opening a message does not reveal anything to the sender.
const document = computed(() => {
  if (!props.message?.body_html) return null
  const policy = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:">`
  const base = '<base target="_blank"><style>body{font:14px/1.6 system-ui,sans-serif;margin:0;padding:4px;color:#1e293b;word-break:break-word}img{max-width:100%}</style>'
  return `<!doctype html><html><head>${policy}${base}</head><body>${props.message.body_html}</body></html>`
})
</script>

<template>
  <UiEmpty v-if="!message" :icon="MailOpen" title="Select a message" text="Messages are copied from your mailbox when you sync." />
  <article v-else class="flex h-full min-h-0 flex-col">
    <header class="border-b border-line pb-4">
      <h2 class="text-lg font-semibold">{{ message.subject || '(no subject)' }}</h2>
      <p class="mt-2 text-sm"><span class="text-muted">From</span> {{ message.sender }}</p>
      <p class="text-sm"><span class="text-muted">To</span> {{ message.recipients }}</p>
      <p v-if="message.cc" class="text-sm"><span class="text-muted">Cc</span> {{ message.cc }}</p>
      <p class="mt-1 text-xs text-muted">{{ formatDateTime(message.received_at) }}</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <UiButton size="sm" @click="$emit('reply', message)"><Reply class="size-3.5" /> Reply</UiButton>
        <UiButton size="sm" :disabled="!canExtract" :title="canExtract ? 'Find dates and deadlines in this message' : 'Needs the assistant to be configured'" @click="$emit('extract', message)">
          <ListPlus class="size-3.5" /> Find deadlines
        </UiButton>
      </div>
    </header>
    <iframe v-if="document" class="mt-4 min-h-[420px] w-full flex-1 rounded-lg border border-line bg-white" sandbox="allow-popups allow-popups-to-escape-sandbox" :srcdoc="document" title="Message content" />
    <div v-else class="mt-4 min-h-0 flex-1 overflow-y-auto text-sm leading-7 whitespace-pre-wrap">{{ message.body_text || message.preview }}</div>
  </article>
</template>
