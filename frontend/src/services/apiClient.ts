const STORAGE_KEY = 'aigent_api_key'

/**
 * Resolve the backend API base URL. Honours VITE_API_BASE_URL when set to an
 * http(s) origin; otherwise defaults to the current page origin. Exposed so
 * callers (e.g. the setup modal's verification probe) can build absolute URLs
 * without re-implementing the resolution logic.
 */
export function getApiBaseUrl(): string {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (explicit && explicit.startsWith('http')) return explicit.replace(/\/+$/, '')
  return location.origin
}

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

// ---------------------------------------------------------------------------
// 401 handling
// ---------------------------------------------------------------------------
// authFetch returns the raw response so callers can branch on status, but a
// 401 almost always means the stored key is missing/wrong. We notify any
// registered listener (the App-level setup modal) so the UI re-prompts without
// every service having to detect it individually.

type AuthFailureListener = () => void
const authFailureListeners = new Set<AuthFailureListener>()

export function onAuthFailure(listener: AuthFailureListener): () => void {
  authFailureListeners.add(listener)
  return () => authFailureListeners.delete(listener)
}

function notifyAuthFailure(): void {
  for (const listener of authFailureListeners) listener()
}

export async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const token = getStoredApiKey()
  const base = new Headers(init.headers)
  if (token) {
    base.set('Authorization', `Bearer ${token}`)
  }
  const response = await fetch(input, { ...init, headers: base })
  if (response.status === 401) {
    notifyAuthFailure()
  }
  return response
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
