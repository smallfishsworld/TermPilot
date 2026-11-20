<script setup lang="ts">
import { CalendarCheck2, KeyRound, ShieldCheck, Sparkles } from '@lucide/vue'
import { useSessionStore } from '~/stores/session'
import { ApiError } from '~/utils/http'

definePageMeta({ layout: 'bare' })
useHead({ title: 'Sign in · TermPilot' })

const session = useSessionStore()
const route = useRoute()
const form = reactive({ username: '', password: '' })
const pending = ref(false)
const problem = ref<string | null>(null)

onMounted(async () => {
  try {
    await session.loadFeatures()
  }
  catch (error) {
    problem.value = error instanceof ApiError ? error.message : 'The TermPilot server cannot be reached.'
  }
})

function useDemo() {
  form.username = 'demo'
  form.password = 'demo'
}

async function submit() {
  pending.value = true
  problem.value = null
  try {
    const result = await session.signIn(form.username.trim(), form.password)
    const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/today'
    await navigateTo(result.first_visit ? { path: '/today', query: { welcome: '1' } } : next)
  }
  catch (error) {
    problem.value = error instanceof ApiError ? error.message : 'Sign-in failed. Please try again.'
  }
  finally {
    pending.value = false
  }
}

const highlights = [
  { icon: CalendarCheck2, title: 'One view of your week', text: 'Classes, deadlines and study time from every campus system, on one timetable.' },
  { icon: Sparkles, title: 'An assistant that checks first', text: 'It reads your data to answer, and asks before it sends, books or changes anything.' },
  { icon: ShieldCheck, title: 'Your password stays yours', text: 'It is used once to sign in to campus services and never stored.' },
]
</script>

<template>
  <div class="mx-auto grid min-h-dvh max-w-6xl items-center gap-12 px-6 py-12 lg:grid-cols-[1.1fr_0.9fr]">
    <section class="hidden lg:block">
      <AppBrand class="text-xl" />
      <h1 class="mt-8 max-w-lg text-4xl leading-tight font-semibold tracking-tight">
        Timetable, deadlines and grades without opening four different websites.
      </h1>
      <ul class="mt-10 space-y-6">
        <li v-for="item in highlights" :key="item.title" class="flex gap-4">
          <div class="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand-strong">
            <component :is="item.icon" class="size-5" />
          </div>
          <div>
            <p class="font-medium">{{ item.title }}</p>
            <p class="mt-0.5 text-sm text-muted">{{ item.text }}</p>
          </div>
        </li>
      </ul>
    </section>

    <section class="panel mx-auto w-full max-w-md p-8 shadow-lg">
      <AppBrand class="lg:hidden" />
      <h2 class="mt-2 text-xl font-semibold lg:mt-0">Sign in</h2>
      <p class="mt-1 text-sm text-muted">Use your campus account. TermPilot signs in to the campus services for you.</p>

      <p v-if="session.expiredNotice" class="mt-5 rounded-lg bg-warn-soft px-3 py-2 text-sm text-warn">
        Your session ended. Please sign in again.
      </p>

      <form class="mt-6 space-y-4" @submit.prevent="submit">
        <div>
          <label class="label" for="username">Student number</label>
          <input id="username" v-model="form.username" class="input" autocomplete="username" inputmode="numeric" required>
        </div>
        <div>
          <label class="label" for="password">Password</label>
          <input id="password" v-model="form.password" class="input" type="password" autocomplete="current-password" required>
        </div>
        <p v-if="problem" class="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{{ problem }}</p>
        <UiButton type="submit" variant="primary" block :loading="pending">
          <KeyRound v-if="!pending" class="size-4" /> Sign in
        </UiButton>
      </form>

      <div v-if="session.features?.demo_mode" class="mt-6 rounded-xl border border-dashed border-brand/40 bg-brand-soft/40 p-4 text-sm">
        <p class="font-medium text-brand-strong">Demo mode is on</p>
        <p class="mt-1 text-muted">Explore with sample data: student number <code>demo</code>, password <code>demo</code>.</p>
        <UiButton size="sm" class="mt-3" @click="useDemo">Fill in the demo account</UiButton>
      </div>
    </section>
  </div>
</template>
