import { defineStore } from 'pinia'
import type { Features, SessionResponse, Student } from '~/types/api'

const TOKEN_KEY = 'termpilot.token'

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  }
  catch {
    return null
  }
}

export const useSessionStore = defineStore('session', () => {
  const token = ref<string | null>(readToken())
  const student = ref<Student | null>(null)
  const features = ref<Features | null>(null)
  const expiredNotice = ref(false)

  const signedIn = computed(() => Boolean(token.value))
  const firstName = computed(() => (student.value?.display_name ?? '').split(/\s+/)[0] ?? '')

  function setToken(value: string | null) {
    token.value = value
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value)
      else localStorage.removeItem(TOKEN_KEY)
    }
    catch {
      // Private browsing may block storage; the session then lasts for this tab only.
    }
  }

  async function loadFeatures(): Promise<Features> {
    features.value = await useHttp().get<Features>('/api/config')
    return features.value
  }

  async function signIn(username: string, password: string): Promise<SessionResponse> {
    const response = await useHttp().post<SessionResponse>('/api/auth/session', { username, password })
    setToken(response.token)
    student.value = response.student
    expiredNotice.value = false
    return response
  }

  async function loadProfile(): Promise<Student | null> {
    if (!token.value) return null
    student.value = await useHttp().get<Student>('/api/me')
    return student.value
  }

  async function updatePreferences(changes: { interests?: string | null, term_start?: string | null, clear_term_start?: boolean }) {
    student.value = await useHttp().patch<Student>('/api/me', changes)
  }

  function clear() {
    setToken(null)
    student.value = null
  }

  async function signOut() {
    try {
      await useHttp().del('/api/auth/session')
    }
    finally {
      clear()
      await navigateTo('/login')
    }
  }

  function expire() {
    if (!token.value) return
    clear()
    expiredNotice.value = true
    navigateTo('/login')
  }

  return { token, student, features, expiredNotice, signedIn, firstName, loadFeatures, signIn, loadProfile, updatePreferences, signOut, expire }
})
