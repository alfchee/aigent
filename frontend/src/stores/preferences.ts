import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark' | 'system'

type PrefsState = {
  theme: ThemeMode
  enterToSend: boolean
  maxMessageLength: number
  sidebarCollapsed: boolean
  e2eeEnabled: boolean
  notificationsEnabled: boolean
}

const LS_KEY = 'navibot:prefs'

function readState(): PrefsState {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) throw new Error('missing')
    const parsed = JSON.parse(raw) as Partial<PrefsState>
    const theme = parsed.theme
    return {
      theme:
        theme === 'light' || theme === 'dark' || theme === 'system' ? theme : 'system',
      enterToSend: parsed.enterToSend ?? true,
      maxMessageLength: Math.max(200, parsed.maxMessageLength ?? 4000),
      sidebarCollapsed: parsed.sidebarCollapsed ?? false,
      e2eeEnabled: parsed.e2eeEnabled ?? false,
      notificationsEnabled: parsed.notificationsEnabled ?? false,
    }
  } catch {
    return {
      theme: 'system',
      enterToSend: true,
      maxMessageLength: 4000,
      sidebarCollapsed: false,
      e2eeEnabled: false,
      notificationsEnabled: false,
    }
  }
}

export const usePreferencesStore = defineStore('preferences', {
  state: (): PrefsState => readState(),
  actions: {
    persist() {
      localStorage.setItem(LS_KEY, JSON.stringify(this.$state))
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      this.persist()
    },
    setTheme(theme: ThemeMode) {
      this.theme = theme
      this.applyThemeToDom()
      this.persist()
    },
    applyThemeToDom() {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      const applied =
        this.theme === 'system' ? (prefersDark ? 'dark' : 'light') : this.theme
      document.documentElement.classList.remove('light', 'dark')
      document.documentElement.classList.add(applied)
    },
    setNotificationsEnabled(enabled: boolean) {
      this.notificationsEnabled = enabled
      this.persist()
    },
  },
})
