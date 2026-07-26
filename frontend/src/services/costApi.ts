import { authFetch } from '@/services/apiClient'

export type LLMCallRecordDto = {
  timestamp: string
  provider: string
  model: string
  input_tokens: number
  output_tokens: number
  cost_usd: number
  session_id: string
  cached: boolean
}

export type SessionCostSummaryDto = {
  session_id: string
  user_id: string
  total_calls: number
  total_input_tokens: number
  total_output_tokens: number
  total_cost_usd: number
  daily_limit_usd: number
  remaining_budget_usd: number
  budget_exceeded: boolean
  last_call_at: string
  currency?: string
}

export type CostSummaryResponseDto = {
  status: string
  sessions?: SessionCostSummaryDto[]
  total_cost_usd?: number
  session_id?: string
  user_id?: string
  total_calls?: number
  total_input_tokens?: number
  total_output_tokens?: number
  daily_limit_usd?: number
  remaining_budget_usd?: number
  budget_exceeded?: boolean
  last_call_at?: string
  not_found?: boolean
}

function getApiBaseUrl(): string {
  const explicit = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (explicit && explicit.startsWith('http')) return explicit.replace(/\/+$/, '')
  return location.origin
}

function buildUrl(path: string): string {
  return new URL(path, `${getApiBaseUrl()}/`).toString()
}

export async function fetchCostSummary(
  sessionId?: string,
): Promise<CostSummaryResponseDto> {
  const url = sessionId
    ? buildUrl(`/cost/summary?session_id=${encodeURIComponent(sessionId)}`)
    : buildUrl('/cost/summary')

  const response = await authFetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })

  if (!response.ok) {
    throw new Error(
      `Failed to fetch cost summary: ${response.status} ${response.statusText}`,
    )
  }

  return response.json() as Promise<CostSummaryResponseDto>
}

export function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`
  if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(1)}K`
  return String(tokens)
}

export function formatCost(costUsd: number): string {
  return `$${costUsd.toFixed(6)}`
}

export function formatRelativeTime(timestamp: string): string {
  const now = Date.now()
  const then = new Date(timestamp).getTime()
  const diffMs = now - then
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffDay > 0) return `hace ${diffDay}d`
  if (diffHour > 0) return `hace ${diffHour}h`
  if (diffMin > 0) return `hace ${diffMin}min`
  if (diffSec > 10) return `hace ${diffSec}s`
  return 'ahora'
}
