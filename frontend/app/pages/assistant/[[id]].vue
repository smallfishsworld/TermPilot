<script setup lang="ts">
import { CalendarPlus, FileStack, Mail, Sparkles, TimerReset } from '@lucide/vue'
import type { AskMode } from '~/types/api'
import { useAssistantStore } from '~/stores/assistant'
import { useSessionStore } from '~/stores/session'
import { useToasts } from '~/stores/toasts'

useHead({ title: 'Assistant · TermPilot' })

const assistant = useAssistantStore()
const session = useSessionStore()
const toasts = useToasts()
const route = useRoute()
const draft = ref('')
const scroller = ref<HTMLElement | null>(null)
const composer = ref<{ focus: () => void } | null>(null)

const conversationId = computed(() => (typeof route.params.id === 'string' ? route.params.id : null))

const starters = [
  { icon: TimerReset, text: 'What is due this week, and what should I start with?' },
  { icon: CalendarPlus, text: 'Find time in my timetable to prepare for my next exam.' },
  { icon: Mail, text: 'Draft a polite email to my instructor asking for a two-day extension.' },
  { icon: FileStack, text: 'Rename the lab files in my workspace to Surname_StudentID_LabN.zip.' },
]

async function openRoute() {
  if (!conversationId.value) {
    assistant.reset()
    return
  }
  if (conversationId.value === assistant.activeId && assistant.turns.length) return
  try {
    await assistant.open(conversationId.value)
    scrollToEnd()
  }
  catch (error) {
    toasts.failure(error)
    await navigateTo('/assistant')
  }
}

function scrollToEnd() {
  nextTick(() => scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' }))
}

async function send(question: string, mode: AskMode, deepThink: boolean) {
  const creating = !assistant.activeId
  const pending = assistant.ask(question, mode, deepThink)
  if (creating) {
    // Wait for the conversation id, then reflect it in the URL without reloading.
    await until(() => assistant.activeId)
    await navigateTo(`/assistant/${assistant.activeId}`, { replace: true })
  }
  scrollToEnd()
  await pending
  scrollToEnd()
}

async function until(check: () => unknown) {
  for (let attempt = 0; attempt < 100 && !check(); attempt++) await new Promise(resolve => setTimeout(resolve, 30))
}

watch(() => assistant.turns.at(-1)?.answer, scrollToEnd)
watch(conversationId, openRoute)

onMounted(async () => {
  await Promise.all([assistant.loadConversations().catch(toasts.failure), session.features ? null : session.loadFeatures().catch(() => null)])
  await openRoute()
  composer.value?.focus()
})
</script>

<template>
  <div class="grid h-[calc(100dvh-8.5rem)] min-h-[520px] gap-4 lg:grid-cols-[17rem_minmax(0,1fr)]">
    <AssistantConversationList class="hidden lg:flex" />

    <section class="flex min-h-0 flex-col">
      <div v-if="session.features && !session.features.assistant" class="mb-3 rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
        The assistant is not configured on this server. Set <code>TP_LLM_API_KEY</code> on the backend to enable it.
      </div>

      <div ref="scroller" class="min-h-0 flex-1 overflow-y-auto pr-1">
        <div v-if="!assistant.turns.length" class="mx-auto flex max-w-2xl flex-col items-center pt-12 text-center">
          <div class="grid size-12 place-items-center rounded-2xl bg-brand-soft text-brand-strong"><Sparkles class="size-6" /></div>
          <h1 class="mt-4 text-xl font-semibold">How can I help this week?</h1>
          <p class="mt-2 text-sm text-muted">
            I can read your timetable, tasks, grades, documents, mail and workspace files. Anything that would send, book or change something
            waits for your approval.
          </p>
          <div class="mt-8 grid w-full gap-3 sm:grid-cols-2">
            <button
              v-for="starter in starters"
              :key="starter.text"
              class="panel flex items-start gap-3 p-4 text-left text-sm transition hover:border-brand/50"
              @click="draft = starter.text; composer?.focus()"
            >
              <component :is="starter.icon" class="mt-0.5 size-4 shrink-0 text-brand" /> {{ starter.text }}
            </button>
          </div>
        </div>
        <div v-else class="mx-auto max-w-3xl space-y-8 py-4">
          <AssistantTurnView v-for="turn in assistant.turns" :key="turn.id" :turn="turn" @ask="question => send(question, turn.mode, false)" />
        </div>
      </div>

      <div class="mx-auto mt-3 w-full max-w-3xl">
        <AssistantComposer ref="composer" v-model="draft" @send="send" />
        <p class="mt-2 text-center text-[0.7rem] text-muted">Answers can be wrong. Check important dates against official notices.</p>
      </div>
    </section>
  </div>
</template>
