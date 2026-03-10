import { fetchWithRetry } from './api'

export interface LLMProvider {
  provider_id: string
  name: string
  base_url?: string
  is_active: boolean
  has_key: boolean
  config?: Record<string, any>
}

export interface LLMModel {
  id: string
  display_name: string
  description?: string
  context_length?: number
  pricing?: any
}

export const llmApi = {
  async getProviders(): Promise<LLMProvider[]> {
    const data = await fetchWithRetry('/api/settings/llm/providers')
    return data.providers
  },

  async saveProvider(config: {
    provider_id: string
    name: string
    api_key?: string
    base_url?: string
    config?: Record<string, any>
  }): Promise<void> {
    await fetchWithRetry('/api/settings/llm/provider', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
  },

  async activateProvider(providerId: string): Promise<void> {
    await fetchWithRetry('/api/settings/llm/activate', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider_id: providerId }),
    })
  },

  async deactivateProvider(providerId: string): Promise<void> {
    await fetchWithRetry('/api/settings/llm/deactivate', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider_id: providerId }),
    })
  },

  async getProviderModels(providerId: string): Promise<LLMModel[]> {
    const data = await fetchWithRetry(`/api/settings/llm/models/${providerId}`)
    return data.models
  },
}
