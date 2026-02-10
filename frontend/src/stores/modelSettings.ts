import { defineStore } from 'pinia'

import { fetchJson } from '../lib/api'

type AppSettingsResponse = {
  settings: {
    current_model: string
    fallback_model: string
    auto_escalate: boolean
    system_prompt: string
    models: string[]
    tiers?: { fast: string[]; fallback: string[] }
    routing_config?: Record<string, any>
    limits_config?: Record<string, any>
    model_routing_json?: Record<string, any>
  }
  providers: Record<string, boolean>
}

type SessionSettingsResponse = {
  session_id: string
  model_name: string | null
}

type ModelInfo = {
  id: string
  display_name: string
  description: string
  input_token_limit?: number
  output_token_limit?: number
}

type AvailableModelsResponse = {
  models: ModelInfo[]
}

export const useModelSettingsStore = defineStore('modelSettings', {
  state: () => ({
    models: [] as string[],
    fastModels: [] as string[],
    fallbackModels: [] as string[],
    availableModels: [] as ModelInfo[],
    currentModel: '' as string,
    fallbackModel: '' as string,
    autoEscalate: true as boolean,
    systemPrompt: '' as string,
    routingConfig: {} as Record<string, any>,
    limitsConfig: {} as Record<string, any>,
    modelRoutingJson: {} as Record<string, any>,
    
    providers: {} as Record<string, boolean>,
    sessionModels: {} as Record<string, string | null>,
    loading: false as boolean,
    error: null as string | null
  }),
  actions: {
    async loadAppSettings() {
      this.loading = true
      this.error = null
      try {
        const [settingsData, modelsData] = await Promise.all([
          fetchJson<AppSettingsResponse>('/api/settings'),
          fetchJson<AvailableModelsResponse>('/api/available-models').catch(() => ({ models: [] }))
        ])
        
        const data = settingsData
        this.availableModels = modelsData.models || []
        
        this.models = data.settings?.models || []
        this.fastModels = data.settings?.tiers?.fast || []
        this.fallbackModels = data.settings?.tiers?.fallback || []
        this.currentModel = data.settings?.current_model || ''
        this.fallbackModel = data.settings?.fallback_model || ''
        this.autoEscalate = Boolean(data.settings?.auto_escalate)
        this.systemPrompt = data.settings?.system_prompt || ''
        
        this.routingConfig = data.settings?.routing_config || {}
        this.limitsConfig = data.settings?.limits_config || {}
        this.modelRoutingJson = data.settings?.model_routing_json || {}
        
        this.providers = data.providers || {}
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
      } finally {
        this.loading = false
      }
    },
    async loadSessionModel(sessionId: string) {
      const sid = sessionId || 'default'
      try {
        const data = await fetchJson<SessionSettingsResponse>(`/api/sessions/${encodeURIComponent(sid)}/settings`)
        this.sessionModels[sid] = data.model_name ?? null
      } catch {
        this.sessionModels[sid] = null
      }
    },
    async setSessionModel(sessionId: string, modelName: string) {
      const sid = sessionId || 'default'
      const name = (modelName || '').trim()
      if (!name) return
      await fetchJson(`/api/sessions/${encodeURIComponent(sid)}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: name })
      })
      this.sessionModels[sid] = name
    },
    async updateAppSettings(payload: {
      current_model?: string
      fallback_model?: string
      auto_escalate?: boolean
      system_prompt?: string
      routing_config?: Record<string, any>
      limits_config?: Record<string, any>
      model_routing_json?: Record<string, any>
    }) {
      this.loading = true
      this.error = null
      try {
        const data = await fetchJson<AppSettingsResponse>('/api/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        this.models = data.settings?.models || []
        this.fastModels = data.settings?.tiers?.fast || []
        this.fallbackModels = data.settings?.tiers?.fallback || []
        this.currentModel = data.settings?.current_model || ''
        this.fallbackModel = data.settings?.fallback_model || ''
        this.autoEscalate = Boolean(data.settings?.auto_escalate)
        this.systemPrompt = data.settings?.system_prompt || ''
        
        this.routingConfig = data.settings?.routing_config || {}
        this.limitsConfig = data.settings?.limits_config || {}
        this.modelRoutingJson = data.settings?.model_routing_json || {}
        
        this.providers = data.providers || {}
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
        throw e
      } finally {
        this.loading = false
      }
    }
  }
})
