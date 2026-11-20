import { useSessionStore } from '~/stores/session'
import { createHttpClient } from '~/utils/http'

// One HTTP client for the whole app. A 401 on an authenticated request means
// the token was revoked or expired, so the session store sends the student
// back to the sign-in page.
export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig()
  const session = useSessionStore()
  const http = createHttpClient(
    config.public.apiBase as string,
    () => session.token,
    () => session.expire(),
  )
  return { provide: { http } }
})
