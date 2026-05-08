const STORAGE_KEY = 'aigent_api_key'

export function getStoredApiKey(): string {
  return localStorage.getItem(STORAGE_KEY) ?? ''
}

export function setStoredApiKey(key: string): void {
  localStorage.setItem(STORAGE_KEY, key)
}

export function clearStoredApiKey(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function hasApiKey(): boolean {
  return getStoredApiKey().length > 0
}

function authHeaders(): HeadersInit {
  const token = getStoredApiKey()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

export async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(input, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init.headers ?? {}),
    },
  })
}

/**
 * Returns the WebSocket URL for a session, appending the Bearer token as a
 * query parameter (browsers cannot set custom WS headers).
 */
export function buildWsUrl(baseUrl: string): string {
  const token = getStoredApiKey()
  if (!token) return baseUrl
  const sep = baseUrl.includes('?') ? '&' : '?'
  return `${baseUrl}${sep}token=${encodeURIComponent(token)}`
}
