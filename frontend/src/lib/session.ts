export function getOrCreateSessionId(storageKey = 'navibot_session_id'): string {
  const existing = localStorage.getItem(storageKey)
  if (existing) return existing
  const sid = generateSessionId()
  localStorage.setItem(storageKey, sid)
  return sid
}

export function setSessionId(sessionId: string, storageKey = 'navibot_session_id') {
  localStorage.setItem(storageKey, sessionId)
}

export function generateSessionId(): string {
  return `s_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`
}
