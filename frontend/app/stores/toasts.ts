import { defineStore } from 'pinia'
import { ApiError } from '~/utils/http'

export interface Toast {
  id: number
  tone: 'info' | 'success' | 'error'
  text: string
}

let counter = 0

export const useToasts = defineStore('toasts', () => {
  const items = ref<Toast[]>([])

  function dismiss(id: number) {
    items.value = items.value.filter(item => item.id !== id)
  }

  function push(tone: Toast['tone'], text: string, timeout = 4500) {
    const id = ++counter
    items.value = [...items.value.slice(-3), { id, tone, text }]
    if (timeout > 0) setTimeout(() => dismiss(id), timeout)
  }

  /** Show what went wrong; API errors already carry a readable message. */
  function failure(error: unknown, fallback = 'Something went wrong.') {
    const text = error instanceof ApiError ? error.message : error instanceof Error && error.name !== 'AbortError' ? error.message || fallback : fallback
    if (error instanceof Error && error.name === 'AbortError') return
    push('error', text, 7000)
  }

  return {
    items,
    dismiss,
    info: (text: string) => push('info', text),
    success: (text: string) => push('success', text),
    failure,
  }
})
