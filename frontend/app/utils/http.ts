// A small fetch wrapper: JSON in and out, bearer auth and one error type.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export interface RequestOptions {
  query?: Record<string, string | number | boolean | null | undefined>
  json?: unknown
  form?: FormData
  signal?: AbortSignal
}

export interface HttpClient {
  request<T>(method: string, path: string, options?: RequestOptions): Promise<T>
  raw(method: string, path: string, options?: RequestOptions): Promise<Response>
  get<T>(path: string, options?: RequestOptions): Promise<T>
  post<T>(path: string, json?: unknown, options?: RequestOptions): Promise<T>
  patch<T>(path: string, json?: unknown, options?: RequestOptions): Promise<T>
  put<T>(path: string, json?: unknown, options?: RequestOptions): Promise<T>
  del(path: string, options?: RequestOptions): Promise<void>
}

export function buildUrl(base: string, path: string, query?: RequestOptions['query']): string {
  const url = new URL(path.replace(/^\//, ''), base.endsWith('/') ? base : `${base}/`)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value))
  }
  return url.toString()
}

export async function toApiError(response: Response): Promise<ApiError> {
  let code = 'http_error'
  let message = `The server answered ${response.status}.`
  let details: unknown
  try {
    const body = await response.json()
    if (body?.error) {
      code = body.error.code ?? code
      message = body.error.message ?? message
      details = body.error.details
    }
  }
  catch {
    // Non-JSON error bodies keep the generic message.
  }
  return new ApiError(response.status, code, message, details)
}

export function createHttpClient(
  baseUrl: string,
  getToken: () => string | null,
  onUnauthorized: (error: ApiError) => void,
): HttpClient {
  async function raw(method: string, path: string, options: RequestOptions = {}): Promise<Response> {
    const headers: Record<string, string> = { Accept: 'application/json, text/event-stream' }
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    let body: BodyInit | undefined
    if (options.form) {
      body = options.form
    }
    else if (options.json !== undefined) {
      headers['Content-Type'] = 'application/json'
      body = JSON.stringify(options.json)
    }
    let response: Response
    try {
      response = await fetch(buildUrl(baseUrl, path, options.query), { method, headers, body, signal: options.signal })
    }
    catch (error) {
      if ((error as Error).name === 'AbortError') throw error
      throw new ApiError(0, 'network_error', 'The TermPilot server cannot be reached. Is it running?')
    }
    if (!response.ok) {
      const error = await toApiError(response)
      if (response.status === 401 && token) onUnauthorized(error)
      throw error
    }
    return response
  }

  async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    const response = await raw(method, path, options)
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  }

  return {
    request,
    raw,
    get: (path, options) => request('GET', path, options),
    post: (path, json, options) => request('POST', path, { ...options, json }),
    patch: (path, json, options) => request('PATCH', path, { ...options, json }),
    put: (path, json, options) => request('PUT', path, { ...options, json }),
    del: async (path, options) => {
      await request('DELETE', path, options)
    },
  }
}
