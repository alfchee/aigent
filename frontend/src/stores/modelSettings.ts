import { defineStore } from 'pinia'

import { ApiError, fetchJson } from '../lib/api'

type RoleConfig = {
  supervisor_model: string
  search_worker_model: string
  code_worker_model: string
  voice_worker_model: string
  scheduled_worker_model: string
  image_worker_model: string
}

type AppSettingsResponse = {
  settings: {
    current_model: string
    fallback_model: string
    auto_escalate: boolean
    emergency_mode: boolean
    system_prompt: string
    models: string[]
    tiers?: { fast: string[]; fallback: string[] }
    routing_config?: Record<string, any>
    role_config?: RoleConfig
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

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const body = error.body
    if (body && typeof body === 'object') {
      const detail = (body as any).detail
      if (typeof detail === 'string') return detail
      if (detail && typeof detail === 'object' && 'message' in detail) {
        return String((detail as any).message)
      }
    }
    if (typeof body === 'string') return body
  }
  return error instanceof Error ? error.message : String(error)
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
    emergencyMode: false as boolean,
    systemPrompt: '' as string,
    routingConfig: {} as Record<string, any>,
    roleConfig: {
      supervisor_model: 'gemini-2.5-pro',
      search_worker_model: 'gemini-2.0-flash',
      code_worker_model: 'gemini-2.0-flash',
      voice_worker_model: 'gemini-flash-latest',
      scheduled_worker_model: 'gemini-flash-latest',
      image_worker_model: 'gemini-2.5-flash-image'
    } as RoleConfig,
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
        this.emergencyMode = Boolean(data.settings?.emergency_mode)
        this.systemPrompt = data.settings?.system_prompt || ''
        
        this.routingConfig = data.settings?.routing_config || {}
        this.roleConfig = data.settings?.role_config || {
          supervisor_model: 'gemini-2.5-pro',
          search_worker_model: 'gemini-2.0-flash',
          code_worker_model: 'gemini-2.0-flash',
          voice_worker_model: 'gemini-flash-latest',
          scheduled_worker_model: 'gemini-flash-latest',
          image_worker_model: 'gemini-2.5-flash-image'
        }
        this.limitsConfig = data.settings?.limits_config || {}
        this.modelRoutingJson = data.settings?.model_routing_json || {}
        
        this.providers = data.providers || {}
      } catch (e) {
        this.error = toErrorMessage(e)
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
      emergency_mode?: boolean
      system_prompt?: string
      routing_config?: Record<string, any>
      role_config?: RoleConfig
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
        this.emergencyMode = Boolean(data.settings?.emergency_mode)
        this.systemPrompt = data.settings?.system_prompt || ''
        
        this.routingConfig = data.settings?.routing_config || {}
        this.roleConfig = data.settings?.role_config || {
          supervisor_model: 'gemini-2.5-pro',
          search_worker_model: 'gemini-2.0-flash',
          code_worker_model: 'gemini-2.0-flash',
          voice_worker_model: 'gemini-flash-latest',
          scheduled_worker_model: 'gemini-flash-latest',
          image_worker_model: 'gemini-2.5-flash-image'
        }
        this.limitsConfig = data.settings?.limits_config || {}
        this.modelRoutingJson = data.settings?.model_routing_json || {}
        
        this.providers = data.providers || {}
      } catch (e) {
        this.error = toErrorMessage(e)
        throw e
      } finally {
        this.loading = false
      }
    }
  }
})
