import type { HttpClient } from '~/utils/http'

export function useHttp(): HttpClient {
  return useNuxtApp().$http as HttpClient
}
