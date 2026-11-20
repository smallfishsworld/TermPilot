<script setup lang="ts">
import { useDebounceFn } from '@vueuse/core'
import { Inbox, MailPlus, Paperclip, PlugZap, RefreshCw, Unplug } from '@lucide/vue'
import type { MailDetail } from '~/types/api'
import { useMailStore } from '~/stores/mail'
import { useSessionStore } from '~/stores/session'
import { useToasts } from '~/stores/toasts'
import { formatDateTime, relativeTime } from '~/utils/format'

useHead({ title: 'Mail · TermPilot' })

const mail = useMailStore()
const session = useSessionStore()
const toasts = useToasts()
const connectForm = reactive({ provider: '', address: '', secret: '' })
const connecting = ref(false)
const compose = reactive({ open: false, preset: null as { to?: string, subject?: string, body?: string } | null })
const extractOpen = ref(false)

const isDemo = computed(() => mail.account?.providers.includes('demo') ?? false)

async function load() {
  try {
    await mail.loadAccount()
    connectForm.provider = mail.account?.providers[0] ?? 'qq'
    await mail.loadMessages()
  }
  catch (error) {
    toasts.failure(error)
  }
}

async function connect() {
  connecting.value = true
  try {
    await mail.connect(connectForm.provider, connectForm.address.trim(), connectForm.secret)
    connectForm.secret = ''
    toasts.success('Mailbox connected.')
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    connecting.value = false
  }
}

async function sync() {
  try {
    const result = await mail.synchronise()
    toasts.success(result.added ? `${result.added} new message(s).` : 'No new messages.')
  }
  catch (error) {
    toasts.failure(error)
  }
}

async function disconnect() {
  if (!confirm('Disconnect this mailbox? Synced messages are removed from TermPilot.')) return
  await mail.disconnect().catch(toasts.failure)
}

function reply(message: MailDetail) {
  const address = message.sender?.match(/<([^>]+)>/)?.[1] ?? message.sender ?? ''
  const quoted = (message.body_text ?? '').split('\n').slice(0, 30).map(line => `> ${line}`).join('\n')
  compose.preset = { to: address, subject: message.subject?.startsWith('Re:') ? message.subject : `Re: ${message.subject ?? ''}`, body: `\n\n${formatDateTime(message.received_at)}, ${message.sender} wrote:\n${quoted}` }
  compose.open = true
}

function newMessage() {
  compose.preset = null
  compose.open = true
}

const refilter = useDebounceFn(() => mail.loadMessages().catch(toasts.failure), 250)
watch(() => [mail.filters.unreadOnly, mail.filters.query], refilter)
onMounted(load)
</script>

<template>
  <div>
    <AppPageHeading title="Mail" :subtitle="mail.connected ? `${mail.account?.address} · synced ${mail.account?.last_synced_at ? relativeTime(mail.account.last_synced_at) : 'never'}` : 'Connect your mailbox to read, search and send from here.'">
      <template v-if="mail.connected">
        <UiButton variant="ghost" @click="disconnect"><Unplug class="size-4" /> Disconnect</UiButton>
        <UiButton :loading="mail.syncing" @click="sync"><RefreshCw v-if="!mail.syncing" class="size-4" /> Sync</UiButton>
        <UiButton variant="primary" @click="newMessage"><MailPlus class="size-4" /> Compose</UiButton>
      </template>
    </AppPageHeading>

    <UiCard v-if="mail.account && !mail.connected" title="Connect a mailbox" class="max-w-xl">
      <form class="space-y-4" @submit.prevent="connect">
        <div>
          <label class="label" for="mail-provider">Provider</label>
          <select id="mail-provider" v-model="connectForm.provider" class="input">
            <option v-for="provider in mail.account.providers" :key="provider" :value="provider">
              {{ { qq: 'QQ Mail', exmail: 'Tencent Exmail (campus mail)', demo: 'Demo mailbox' }[provider] ?? provider }}
            </option>
          </select>
        </div>
        <div>
          <label class="label" for="mail-address">Email address</label>
          <input id="mail-address" v-model="connectForm.address" class="input" type="email" required autocomplete="email">
        </div>
        <div>
          <label class="label" for="mail-secret">Authorization code</label>
          <input id="mail-secret" v-model="connectForm.secret" class="input" type="password" required autocomplete="off">
          <p class="mt-1 text-xs text-muted">
            {{ isDemo ? 'Demo mode: use any address and the code "demo".' : 'Create an IMAP/SMTP authorization code in your mailbox settings; it is not your login password. It is stored encrypted and removed when you disconnect.' }}
          </p>
        </div>
        <UiButton type="submit" variant="primary" :loading="connecting"><PlugZap v-if="!connecting" class="size-4" /> Connect</UiButton>
      </form>
    </UiCard>

    <div v-else-if="mail.connected" class="grid h-[calc(100dvh-12rem)] min-h-[480px] gap-4 lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
      <section class="panel flex min-h-0 flex-col">
        <div class="flex items-center gap-3 border-b border-line p-3">
          <input v-model="mail.filters.query" class="input" type="search" placeholder="Search subject or sender">
          <UiToggle v-model="mail.filters.unreadOnly" label="Unread" />
        </div>
        <UiEmpty v-if="!mail.messages.length" :icon="Inbox" title="No messages" text="Press Sync to fetch the latest messages." />
        <ul class="min-h-0 flex-1 divide-y divide-line overflow-y-auto">
          <li v-for="item in mail.messages" :key="item.id">
            <button
              class="w-full px-4 py-3 text-left transition hover:bg-surface-muted"
              :class="mail.selected?.id === item.id ? 'bg-brand-soft/50' : ''"
              @click="mail.select(item.id).catch(toasts.failure)"
            >
              <div class="flex items-center gap-2">
                <span v-if="!item.seen" class="size-2 shrink-0 rounded-full bg-brand" aria-label="Unread" />
                <p class="min-w-0 flex-1 truncate text-sm" :class="item.seen ? '' : 'font-semibold'">{{ item.sender?.replace(/<.*>/, '').trim() || 'Unknown sender' }}</p>
                <Paperclip v-if="item.has_attachments" class="size-3.5 text-muted" />
                <span class="text-xs text-muted">{{ item.received_at ? relativeTime(item.received_at) : '' }}</span>
              </div>
              <p class="mt-0.5 truncate text-sm">{{ item.subject || '(no subject)' }}</p>
              <p class="mt-0.5 line-clamp-2 text-xs text-muted">{{ item.preview }}</p>
            </button>
          </li>
        </ul>
      </section>
      <section class="panel min-h-0 overflow-y-auto p-5">
        <MailReader :message="mail.selected" :can-extract="session.features?.assistant ?? false" @reply="reply" @extract="extractOpen = true" />
      </section>
    </div>

    <MailComposeDialog v-model:open="compose.open" :preset="compose.preset" />
    <MailTaskCandidatesDialog v-model:open="extractOpen" :message="mail.selected" />
  </div>
</template>
