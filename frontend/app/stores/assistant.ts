import { defineStore } from 'pinia'
import type { Approval, AskMode, Attachment, ConversationDetail, ConversationSummary, Source, Step, Turn } from '~/types/api'
import { readEventStream } from '~/utils/sse'

export interface LiveTurn extends Turn {
  streaming: boolean
  approvals: Approval[]
  error: string | null
}

function blankTurn(question: string, mode: AskMode): LiveTurn {
  return {
    id: `pending-${Date.now()}`,
    mode,
    question,
    answer: '',
    reasoning: null,
    sources: [],
    suggestions: [],
    trace: [],
    failed: false,
    created_at: new Date().toISOString(),
    streaming: true,
    approvals: [],
    error: null,
  }
}

export const useAssistantStore = defineStore('assistant', () => {
  const conversations = ref<ConversationSummary[]>([])
  const activeId = ref<string | null>(null)
  const turns = ref<LiveTurn[]>([])
  const attachments = ref<Attachment[]>([])
  const approvals = ref<Record<string, Approval>>({})
  const busy = ref(false)
  let controller: AbortController | null = null

  const active = computed(() => conversations.value.find(item => item.id === activeId.value) ?? null)
  const pendingApprovals = computed(() => Object.values(approvals.value).filter(item => item.status === 'pending'))

  async function loadConversations(query = '') {
    conversations.value = await useHttp().get<ConversationSummary[]>('/api/conversations', { query: { q: query } })
  }

  async function open(id: string) {
    const detail = await useHttp().get<ConversationDetail>(`/api/conversations/${id}`)
    activeId.value = id
    attachments.value = detail.attachments
    approvals.value = Object.fromEntries(detail.approvals.map(item => [item.id, item]))
    // Proposals are listed per conversation; show them under the turn that made them.
    turns.value = detail.turns.map((turn, index) => {
      const next = detail.turns[index + 1]?.created_at ?? '9999'
      return {
        ...turn,
        streaming: false,
        error: turn.failed ? 'This answer did not complete.' : null,
        approvals: detail.approvals.filter(item => item.created_at && turn.created_at <= item.created_at && item.created_at < next),
      }
    })
    const summary = conversations.value.find(item => item.id === id)
    if (!summary) conversations.value = [detail.conversation, ...conversations.value]
  }

  async function create(): Promise<string> {
    const conversation = await useHttp().post<ConversationSummary>('/api/conversations', {})
    conversations.value = [conversation, ...conversations.value]
    activeId.value = conversation.id
    turns.value = []
    attachments.value = []
    approvals.value = {}
    return conversation.id
  }

  async function rename(id: string, title: string) {
    const updated = await useHttp().patch<ConversationSummary>(`/api/conversations/${id}`, { title })
    conversations.value = conversations.value.map(item => (item.id === id ? { ...item, title: updated.title } : item))
  }

  async function remove(id: string) {
    await useHttp().del(`/api/conversations/${id}`)
    conversations.value = conversations.value.filter(item => item.id !== id)
    if (activeId.value === id) {
      activeId.value = null
      turns.value = []
    }
  }

  async function attach(file: File) {
    if (!activeId.value) await create()
    const form = new FormData()
    form.append('file', file)
    const attachment = await useHttp().request<Attachment>('POST', `/api/conversations/${activeId.value}/attachments`, { form })
    attachments.value = [...attachments.value, attachment]
  }

  async function detach(id: number) {
    await useHttp().del(`/api/conversations/${activeId.value}/attachments/${id}`)
    attachments.value = attachments.value.filter(item => item.id !== id)
  }

  function upsertStep(turn: LiveTurn, step: Step) {
    const index = turn.trace.findIndex(item => item.id === step.id)
    if (index === -1) turn.trace.push(step)
    else turn.trace.splice(index, 1, step)
  }

  async function ask(question: string, mode: AskMode, deepThink: boolean) {
    if (busy.value || !question.trim()) return
    const conversationId = activeId.value ?? (await create())
    const live = reactive(blankTurn(question.trim(), mode)) as LiveTurn
    turns.value.push(live)
    busy.value = true
    controller = new AbortController()
    try {
      const response = await useHttp().raw('POST', `/api/conversations/${conversationId}/ask`, {
        json: { question: live.question, mode, deep_think: deepThink },
        signal: controller.signal,
      })
      await readEventStream(response, ({ event, data }) => {
        switch (event) {
          case 'turn': live.id = data.turn_id; break
          case 'step': upsertStep(live, data as Step); break
          case 'sources': live.sources = data.items as Source[]; break
          case 'reasoning': live.reasoning = (live.reasoning ?? '') + data.text; break
          case 'answer': live.answer += data.text; break
          case 'approval': {
            const approval = data as Approval
            approvals.value[approval.id] = approval
            live.approvals.push(approval)
            break
          }
          case 'suggestions': live.suggestions = data.items; break
          case 'title':
            conversations.value = conversations.value.map(item => (item.id === conversationId ? { ...item, title: data.title } : item))
            break
          case 'error': live.error = data.message; live.failed = !live.answer; break
        }
      })
    }
    catch (error) {
      if ((error as Error).name === 'AbortError') live.error = 'Stopped.'
      else live.error = (error as Error).message
    }
    finally {
      live.streaming = false
      busy.value = false
      controller = null
      const summary = conversations.value.find(item => item.id === conversationId)
      if (summary) {
        summary.updated_at = new Date().toISOString()
        summary.turn_count += 1
        conversations.value = [summary, ...conversations.value.filter(item => item.id !== conversationId)]
      }
    }
  }

  function stop() {
    controller?.abort()
  }

  async function decide(id: string, approve: boolean) {
    const result = await useHttp().post<Approval>(`/api/approvals/${id}/decision`, { approve })
    approvals.value[id] = result
    for (const turn of turns.value) {
      turn.approvals = turn.approvals.map(item => (item.id === id ? result : item))
    }
    return result
  }

  function reset() {
    activeId.value = null
    turns.value = []
    attachments.value = []
    approvals.value = {}
  }

  return {
    conversations, activeId, active, turns, attachments, approvals, pendingApprovals, busy,
    loadConversations, open, create, rename, remove, attach, detach, ask, stop, decide, reset,
  }
})
