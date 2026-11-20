<script setup lang="ts">
import { Send } from '@lucide/vue'
import { useMailStore } from '~/stores/mail'
import { useToasts } from '~/stores/toasts'

const props = defineProps<{ preset?: { to?: string, subject?: string, body?: string } | null }>()
const open = defineModel<boolean>('open', { default: false })
const mail = useMailStore()
const toasts = useToasts()
const form = reactive({ to: '', cc: '', subject: '', body: '' })
const sending = ref(false)

watch(open, (value) => {
  if (value) Object.assign(form, { to: props.preset?.to ?? '', cc: '', subject: props.preset?.subject ?? '', body: props.preset?.body ?? '' })
})

const split = (value: string) => value.split(/[,;\s]+/).map(item => item.trim()).filter(Boolean)

async function send() {
  sending.value = true
  try {
    await mail.send({ to: split(form.to), cc: split(form.cc), subject: form.subject, body: form.body })
    toasts.success('Message sent.')
    open.value = false
  }
  catch (error) {
    toasts.failure(error)
  }
  finally {
    sending.value = false
  }
}
</script>

<template>
  <UiDialog v-model:open="open" title="New message" :description="`From ${mail.account?.address ?? ''}`" wide>
    <form id="compose-form" class="space-y-3" @submit.prevent="send">
      <div>
        <label class="label" for="compose-to">To</label>
        <input id="compose-to" v-model="form.to" class="input" required placeholder="name@example.edu, …">
      </div>
      <div>
        <label class="label" for="compose-cc">Cc</label>
        <input id="compose-cc" v-model="form.cc" class="input">
      </div>
      <div>
        <label class="label" for="compose-subject">Subject</label>
        <input id="compose-subject" v-model="form.subject" class="input" required maxlength="300">
      </div>
      <div>
        <label class="label" for="compose-body">Message</label>
        <textarea id="compose-body" v-model="form.body" class="input min-h-56" required />
      </div>
    </form>
    <template #footer>
      <UiButton @click="open = false">Discard</UiButton>
      <UiButton type="submit" form="compose-form" variant="primary" :loading="sending"><Send v-if="!sending" class="size-4" /> Send</UiButton>
    </template>
  </UiDialog>
</template>
