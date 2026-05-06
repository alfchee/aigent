export type SoulResponse = {
  status: string
  soul: string
}

// ---------------------------------------------------------------------------
// Provider types
// ---------------------------------------------------------------------------

export type ProviderStatusValue = 'configured' | 'missing' | 'untested'

export type ProviderStatus = {
  name: string
  label: string
  status: ProviderStatusValue
  has_key: boolean
  base_url: string | null
  default_model: string | null
  available_models: string[]
  needs_key: boolean
}

export type ProvidersResponse = {
  providers: ProviderStatus[]
}

export type ProviderUpdate = {
  name: string
  api_key?: string | null
  base_url?: string | null
  default_model?: string | null
}

export type TestProviderResult = {
  success: boolean
  message: string
  latency_ms: number | null
}

export type ProviderModels = {
  provider: string
  models: string[]
}

// ---------------------------------------------------------------------------
// Base URL helpers
// ---------------------------------------------------------------------------

function getApiBaseUrl() {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (explicit && explicit.startsWith('http')) return explicit.replace(/\/+$/, '')
  return location.origin
}

function buildUrl(path: string) {
  return new URL(path, `${getApiBaseUrl()}/`).toString()
}

export async function fetchSoulPrompt(): Promise<string> {
  const response = await fetch(buildUrl('/config/soul'), { method: 'GET' })
  if (!response.ok) {
    throw new Error(`Failed to fetch soul prompt: ${response.status}`)
  }
  const data = (await response.json()) as SoulResponse
  return data.soul
}

export async function updateSoulPrompt(soul: string): Promise<string> {
  const response = await fetch(buildUrl('/config/soul'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ soul }),
  })
  if (!response.ok) {
    throw new Error(`Failed to update soul prompt: ${response.status}`)
  }
  const data = (await response.json()) as SoulResponse
  return data.soul
}

// ---------------------------------------------------------------------------
// Provider API functions
// ---------------------------------------------------------------------------

export async function fetchProviders(): Promise<ProviderStatus[]> {
  const response = await fetch(buildUrl('/config/providers'), { method: 'GET' })
  if (!response.ok) {
    throw new Error(`Failed to fetch providers: ${response.status}`)
  }
  const data = (await response.json()) as ProvidersResponse
  return data.providers
}

export async function updateProviders(
  updates: ProviderUpdate[],
): Promise<ProviderStatus[]> {
  const response = await fetch(buildUrl('/config/providers'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ providers: updates }),
  })
  if (!response.ok) {
    throw new Error(`Failed to update providers: ${response.status}`)
  }
  const data = (await response.json()) as ProvidersResponse
  return data.providers
}

export async function testProvider(name: string): Promise<TestProviderResult> {
  const response = await fetch(
    buildUrl(`/config/providers/${encodeURIComponent(name)}/test`),
    {
      method: 'POST',
    },
  )
  if (!response.ok) {
    throw new Error(`Failed to test provider: ${response.status}`)
  }
  return (await response.json()) as TestProviderResult
}

export async function fetchProviderModels(name: string): Promise<string[]> {
  const response = await fetch(
    buildUrl(`/config/providers/${encodeURIComponent(name)}/models`),
    { method: 'GET' },
  )
  if (!response.ok) {
    throw new Error(`Failed to fetch models for ${name}: ${response.status}`)
  }
  const data = (await response.json()) as ProviderModels
  return data.models
}
