import { defineStore } from 'pinia'
import { fetchJson } from '../lib/api'

export type Provider = {
  provider_id: string
  name: string
  base_url?: string
  is_active: boolean
  has_key: boolean
}

type ProvidersResponse = {
  providers: Provider[]
}

const STORAGE_KEY = 'navibot_selected_provider'

export const useProviderStore = defineStore('providers', {
  state: () => ({
    availableProviders: [] as Provider[],
    selectedProvider: '' as string,
    loading: false,
    error: null as string | null,
  }),

  getters: {
    activeProviders: (state) => state.availableProviders.filter((p) => p.is_active),

    providerLabel: (state) => (providerId: string) => {
      const provider = state.availableProviders.find((p) => p.provider_id === providerId)
      return provider?.name || providerId
    },
  },

  actions: {
    async loadProviders() {
      this.loading = true
      this.error = null
      try {
        const data = await fetchJson<ProvidersResponse>('/api/settings/llm/providers')
        this.availableProviders = data.providers || []
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
        console.error('Failed to load providers:', e)
      } finally {
        this.loading = false
      }
    },

    setProvider(providerId: string) {
      this.selectedProvider = providerId
      // Persist to localStorage
      localStorage.setItem(STORAGE_KEY, providerId)
    },

    loadFromStorage() {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        this.selectedProvider = stored
      }
    },

    clearProvider() {
      this.selectedProvider = ''
      localStorage.removeItem(STORAGE_KEY)
    },
  },
})
