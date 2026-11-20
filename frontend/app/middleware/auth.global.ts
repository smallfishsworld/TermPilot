import { useSessionStore } from '~/stores/session'

const PUBLIC_ROUTES = new Set(['/login'])

export default defineNuxtRouteMiddleware(async (to) => {
  const session = useSessionStore()
  if (PUBLIC_ROUTES.has(to.path)) {
    return session.signedIn ? navigateTo('/today') : undefined
  }
  if (!session.signedIn) {
    return navigateTo({ path: '/login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} })
  }
  if (!session.student || !session.features) {
    try {
      // Pages decide what to offer (assistant, library, web search) from the feature flags.
      await Promise.all([session.student ? null : session.loadProfile(), session.features ? null : session.loadFeatures()])
    }
    catch {
      // A revoked token triggers session.expire(); other failures surface on the page.
    }
  }
  if (to.path === '/') return navigateTo('/today')
})
