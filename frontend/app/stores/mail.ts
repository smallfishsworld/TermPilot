import { defineStore } from 'pinia'
import type { MailAccount, MailDetail, MailSummary, TaskCandidate } from '~/types/api'

export const useMailStore = defineStore('mail', () => {
  const account = ref<MailAccount | null>(null)
  const messages = ref<MailSummary[]>([])
  const selected = ref<MailDetail | null>(null)
  const filters = reactive({ unreadOnly: false, query: '' })
  const syncing = ref(false)

  const connected = computed(() => account.value?.connected ?? false)

  async function loadAccount() {
    account.value = await useHttp().get<MailAccount>('/api/mail/account')
  }

  async function connect(provider: string, address: string, secret: string) {
    account.value = await useHttp().put<MailAccount>('/api/mail/account', { provider, address, secret })
    await synchronise()
  }

  async function disconnect() {
    await useHttp().del('/api/mail/account')
    messages.value = []
    selected.value = null
    await loadAccount()
  }

  async function loadMessages() {
    if (!connected.value) return
    messages.value = await useHttp().get<MailSummary[]>('/api/mail/messages', {
      query: { unread_only: filters.unreadOnly, q: filters.query.trim(), limit: 100 },
    })
  }

  async function synchronise() {
    syncing.value = true
    try {
      const result = await useHttp().post<{ fetched: number, added: number }>('/api/mail/sync', { limit: 40 })
      await Promise.all([loadMessages(), loadAccount()])
      return result
    }
    finally {
      syncing.value = false
    }
  }

  async function select(id: number) {
    selected.value = await useHttp().get<MailDetail>(`/api/mail/messages/${id}`)
  }

  async function send(input: { to: string[], cc: string[], subject: string, body: string }) {
    return useHttp().post<{ message_id: string }>('/api/mail/send', { ...input, bcc: [] })
  }

  async function findTasks(id: number) {
    return useHttp().post<TaskCandidate[]>(`/api/mail/messages/${id}/tasks`)
  }

  return { account, messages, selected, filters, syncing, connected, loadAccount, connect, disconnect, loadMessages, synchronise, select, send, findTasks }
})
