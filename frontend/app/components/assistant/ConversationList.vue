<script setup lang="ts">
import { useDebounceFn } from '@vueuse/core'
import { MessagesSquare, Pencil, Plus, Trash2 } from '@lucide/vue'
import { useAssistantStore } from '~/stores/assistant'
import { useToasts } from '~/stores/toasts'
import { relativeTime } from '~/utils/format'

const assistant = useAssistantStore()
const toasts = useToasts()
const query = ref('')

const search = useDebounceFn(() => assistant.loadConversations(query.value).catch(toasts.failure), 250)
watch(query, search)

function startNew() {
  assistant.reset()
  navigateTo('/assistant')
}

async function rename(id: string, current: string) {
  const title = prompt('Rename conversation', current)?.trim()
  if (!title || title === current) return
  await assistant.rename(id, title).catch(toasts.failure)
}

async function remove(id: string) {
  if (!confirm('Delete this conversation and its history?')) return
  await assistant.remove(id).catch(toasts.failure)
  if (!assistant.activeId) await navigateTo('/assistant')
}
</script>

<template>
  <aside class="panel flex min-h-0 flex-col">
    <div class="space-y-2 border-b border-line p-3">
      <UiButton variant="primary" block @click="startNew"><Plus class="size-4" /> New conversation</UiButton>
      <input v-model="query" class="input" type="search" placeholder="Search titles">
    </div>
    <nav class="min-h-0 flex-1 overflow-y-auto p-2" aria-label="Conversations">
      <UiEmpty v-if="!assistant.conversations.length" :icon="MessagesSquare" title="No conversations yet" />
      <NuxtLink
        v-for="conversation in assistant.conversations"
        :key="conversation.id"
        :to="`/assistant/${conversation.id}`"
        class="group flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-surface-muted"
        :class="conversation.id === assistant.activeId ? 'bg-brand-soft/60 text-brand-strong' : ''"
      >
        <div class="min-w-0 flex-1">
          <p class="truncate font-medium">{{ conversation.title }}</p>
          <p class="text-xs text-muted">{{ relativeTime(conversation.updated_at) }} · {{ conversation.turn_count }} message{{ conversation.turn_count === 1 ? '' : 's' }}</p>
        </div>
        <button class="hidden rounded p-1 text-muted group-hover:block hover:text-ink" aria-label="Rename" @click.prevent="rename(conversation.id, conversation.title)"><Pencil class="size-3.5" /></button>
        <button class="hidden rounded p-1 text-muted group-hover:block hover:text-danger" aria-label="Delete" @click.prevent="remove(conversation.id)"><Trash2 class="size-3.5" /></button>
      </NuxtLink>
    </nav>
  </aside>
</template>
