<script setup lang="ts">
import { Brain, ChevronDown, CircleAlert, CircleCheck, ExternalLink, FileText, Globe, LoaderCircle, Paperclip, Wrench } from '@lucide/vue'
import type { LiveTurn } from '~/stores/assistant'
import { renderAnswer } from '~/utils/markdown'

const props = defineProps<{ turn: LiveTurn }>()
defineEmits<{ ask: [question: string] }>()

const showTrace = ref(false)
const showReasoning = ref(false)
const highlighted = ref<number | null>(null)

const html = computed(() => renderAnswer(props.turn.answer, props.turn.sources.length))
const waiting = computed(() => props.turn.streaming && !props.turn.answer)
const runningStep = computed(() => [...props.turn.trace].reverse().find(step => step.status === 'running'))
const sourceIcon = { library: FileText, web: Globe, attachment: Paperclip }
const modeLabel = { agent: 'Agent', ask: 'Ask', research: 'Research' }

function onAnswerClick(event: MouseEvent) {
  const target = (event.target as HTMLElement).closest('[data-source]') as HTMLElement | null
  if (!target) return
  highlighted.value = Number(target.dataset.source)
  document.getElementById(`source-${props.turn.id}-${highlighted.value}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}
</script>

<template>
  <article class="space-y-4">
    <div class="flex justify-end">
      <div class="max-w-[85%] rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-sm whitespace-pre-wrap text-white shadow-sm dark:text-page">{{ turn.question }}</div>
    </div>

    <div class="flex gap-3">
      <div class="mt-1 grid size-8 shrink-0 place-items-center rounded-full bg-brand-soft text-xs font-bold text-brand-strong">T</div>
      <div class="min-w-0 flex-1 space-y-3">
        <div v-if="turn.trace.length" class="rounded-xl border border-line bg-surface">
          <button class="flex w-full items-center gap-2 px-3 py-2 text-xs text-muted" @click="showTrace = !showTrace">
            <Wrench class="size-3.5" />
            <span v-if="runningStep" class="text-ink">{{ runningStep.label }}…</span>
            <span v-else>Used {{ turn.trace.length }} tool{{ turn.trace.length === 1 ? '' : 's' }} · {{ modeLabel[turn.mode] }}</span>
            <ChevronDown class="ml-auto size-3.5 transition" :class="showTrace ? 'rotate-180' : ''" />
          </button>
          <ol v-if="showTrace" class="space-y-1.5 border-t border-line px-3 py-2">
            <li v-for="step in turn.trace" :key="step.id" class="flex items-start gap-2 text-xs">
              <LoaderCircle v-if="step.status === 'running'" class="mt-0.5 size-3.5 shrink-0 animate-spin text-brand" />
              <CircleCheck v-else-if="step.status === 'done'" class="mt-0.5 size-3.5 shrink-0 text-ok" />
              <CircleAlert v-else class="mt-0.5 size-3.5 shrink-0 text-danger" />
              <span><b class="font-medium">{{ step.label }}</b><span v-if="step.detail" class="text-muted"> — {{ step.detail }}</span></span>
            </li>
          </ol>
        </div>

        <div v-if="turn.reasoning" class="rounded-xl border border-dashed border-line">
          <button class="flex w-full items-center gap-2 px-3 py-2 text-xs text-muted" @click="showReasoning = !showReasoning">
            <Brain class="size-3.5" /> {{ turn.streaming && !turn.answer ? 'Thinking…' : 'Show reasoning' }}
            <ChevronDown class="ml-auto size-3.5 transition" :class="showReasoning ? 'rotate-180' : ''" />
          </button>
          <p v-if="showReasoning" class="border-t border-dashed border-line px-3 py-2 text-xs leading-6 whitespace-pre-wrap text-muted">{{ turn.reasoning }}</p>
        </div>

        <div v-if="waiting" class="flex items-center gap-1 py-2" aria-label="Working">
          <span v-for="n in 3" :key="n" class="typing-dot size-1.5 rounded-full bg-muted" />
        </div>
        <!-- eslint-disable-next-line vue/no-v-html -- rendered with raw HTML disabled -->
        <div v-if="turn.answer" class="answer" @click="onAnswerClick" v-html="html" />

        <div v-for="approval in turn.approvals" :key="approval.id">
          <AssistantApprovalCard :approval="approval" />
        </div>

        <p v-if="turn.error" class="flex items-start gap-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
          <CircleAlert class="mt-0.5 size-4 shrink-0" /> {{ turn.error }}
        </p>

        <div v-if="turn.sources.length" class="grid gap-2 sm:grid-cols-2">
          <component
            :is="source.url ? 'a' : 'div'"
            v-for="source in turn.sources"
            :id="`source-${turn.id}-${source.index}`"
            :key="source.index"
            :href="source.url ?? undefined"
            target="_blank"
            rel="noopener noreferrer"
            class="group rounded-xl border bg-surface p-3 text-xs transition"
            :class="highlighted === source.index ? 'border-brand ring-2 ring-brand/20' : 'border-line hover:border-brand/40'"
          >
            <p class="flex items-center gap-1.5 font-medium text-ink">
              <span class="cite !ml-0">{{ source.index }}</span>
              <component :is="sourceIcon[source.kind]" class="size-3.5 text-muted" />
              <span class="truncate">{{ source.title }}</span>
              <ExternalLink v-if="source.url" class="ml-auto size-3 text-muted opacity-0 group-hover:opacity-100" />
            </p>
            <p class="mt-1 line-clamp-3 text-muted">{{ source.excerpt }}</p>
          </component>
        </div>

        <div v-if="turn.suggestions.length && !turn.streaming" class="flex flex-wrap gap-2">
          <button v-for="question in turn.suggestions" :key="question" class="chip hover:border-brand hover:text-brand" @click="$emit('ask', question)">
            {{ question }}
          </button>
        </div>
      </div>
    </div>
  </article>
</template>
