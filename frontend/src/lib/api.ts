export class ApiError extends Error {
  status: number
  body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export class NetworkError extends Error {
  originalError: unknown
  constructor(message: string, originalError?: unknown) {
    super(message)
    this.name = 'NetworkError'
    this.originalError = originalError
  }
}

export class TimeoutError extends Error {
  constructor(timeout: number) {
    super(`Request timed out after ${timeout}ms`)
    this.name = 'TimeoutError'
  }
}

export interface FetchOptions extends RequestInit {
  retries?: number
  retryDelay?: number
  timeout?: number
}

const DEFAULT_RETRIES = 3
const DEFAULT_RETRY_DELAY = 1000
const DEFAULT_TIMEOUT = 10000

async function fetchWithRetry(input: RequestInfo | URL, init?: FetchOptions): Promise<Response> {
  const retries = init?.retries ?? DEFAULT_RETRIES
  const retryDelay = init?.retryDelay ?? DEFAULT_RETRY_DELAY
  const timeout = init?.timeout ?? DEFAULT_TIMEOUT

  let lastError: unknown

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    // Combine user signal with timeout signal if needed (simplified here)
    // Note: If init.signal is provided and aborted, we should respect it.

    try {
      const res = await fetch(input, {
        ...init,
        signal: controller.signal,
      })
      clearTimeout(timeoutId)
      return res
    } catch (err: any) {
      clearTimeout(timeoutId)
      lastError = err

      // Handle Timeout
      if (err.name === 'AbortError') {
        // Check if the user passed a signal that is aborted
        if (init?.signal?.aborted) {
          throw err // User aborted manually
        }
        // Otherwise it's our timeout
        throw new TimeoutError(timeout)
      }

      // If it's not a network error (e.g. strict CORS might throw), we might still want to retry if it's transient.
      // But usually fetch throws TypeError for network issues.

      const isNetworkError = err instanceof TypeError || err.name === 'TypeError'
      if (!isNetworkError) {
        throw err // Logic error or other non-retriable error
      }

      if (attempt === retries) break

      // Exponential backoff with jitter
      const delay = retryDelay * Math.pow(2, attempt) + Math.random() * 100
      await new Promise((resolve) => setTimeout(resolve, delay))
    }
  }

  throw new NetworkError(
    `Network request failed after ${retries + 1} attempts. Please check your connection.`,
    lastError,
  )
}

async function parseJsonSafely(res: Response): Promise<unknown> {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export async function fetchJson<T>(input: RequestInfo | URL, init?: FetchOptions): Promise<T> {
  const res = await fetchWithRetry(input, init)
  if (!res.ok) {
    const body = await parseJsonSafely(res)
    throw new ApiError('Request failed', res.status, body)
  }
  return (await res.json()) as T
}

export async function fetchText(input: RequestInfo | URL, init?: FetchOptions): Promise<string> {
  const res = await fetchWithRetry(input, init)
  if (!res.ok) {
    const body = await parseJsonSafely(res)
    throw new ApiError('Request failed', res.status, body)
  }
  return await res.text()
}

export async function fetchBlob(input: RequestInfo | URL, init?: FetchOptions): Promise<Blob> {
  const res = await fetchWithRetry(input, init)
  if (!res.ok) {
    const body = await parseJsonSafely(res)
    throw new ApiError('Request failed', res.status, body)
  }
  return await res.blob()
}
