import { defineStore } from 'pinia'

type UserConfigState = {
  sessionId: string
  displayName: string
  activeAgentId: string
}

const LS_KEY = 'navibot:user'

function getOrCreateSessionId() {
  const existing = localStorage.getItem('navibot:session')
  if (existing) return existing
  const id = crypto.randomUUID()
  localStorage.setItem('navibot:session', id)
  return id
}

function readState(): UserConfigState {
  const base: UserConfigState = {
    sessionId: getOrCreateSessionId(),
    displayName: 'Tú',
    activeAgentId: 'default',
  }
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return base
    const parsed = JSON.parse(raw) as Partial<UserConfigState>
    return {
      sessionId: base.sessionId,
      displayName:
        typeof parsed.displayName === 'string' && parsed.displayName
          ? parsed.displayName
          : base.displayName,
      activeAgentId:
        typeof parsed.activeAgentId === 'string' && parsed.activeAgentId
          ? parsed.activeAgentId
          : base.activeAgentId,
    }
  } catch {
    return base
  }
}

export const useUserConfigStore = defineStore('userConfig', {
  state: (): UserConfigState => readState(),
  actions: {
    persist() {
      localStorage.setItem(
        LS_KEY,
        JSON.stringify({
          displayName: this.displayName,
          activeAgentId: this.activeAgentId,
        }),
      )
    },
    setDisplayName(name: string) {
      this.displayName = name
      this.persist()
    },
    setActiveAgentId(id: string) {
      this.activeAgentId = id
      this.persist()
    },
  },
})
