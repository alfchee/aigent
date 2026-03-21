import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SessionCostSummaryDto } from '@/services/costApi'
import { fetchCostSummary } from '@/services/costApi'

export const useCostStore = defineStore('cost', () => {
  const summariesBySession = ref<Record<string, SessionCostSummaryDto>>({})
  const currentSessionId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const lastRefresh = ref<number | null>(null)

  const currentSummary = computed<SessionCostSummaryDto | null>(() => {
    if (!currentSessionId.value) return null
    return summariesBySession.value[currentSessionId.value] ?? null
  })

  const allSessions = computed<SessionCostSummaryDto[]>(() => {
    return Object.values(summariesBySession.value)
  })

  const totalCost = computed<number>(() => {
    return allSessions.value.reduce((sum, s) => sum + (s.total_cost_usd ?? 0), 0)
  })

  const budgetPercentageUsed = computed<number>(() => {
    const summary = currentSummary.value
    if (!summary || summary.daily_limit_usd <= 0) return 0
    const spent = summary.daily_limit_usd - summary.remaining_budget_usd
    return Math.min(100, (spent / summary.daily_limit_usd) * 100)
  })

  function normalizeSession(dto: SessionCostSummaryDto): SessionCostSummaryDto {
    return {
      ...dto,
      daily_limit_usd: dto.daily_limit_usd ?? 10,
      remaining_budget_usd:
        typeof dto.remaining_budget_usd === 'number'
          ? dto.remaining_budget_usd
          : Math.max(0, (dto.daily_limit_usd ?? 10) - (dto.total_cost_usd ?? 0)),
      budget_exceeded:
        typeof dto.budget_exceeded === 'boolean'
          ? dto.budget_exceeded
          : (dto.total_cost_usd ?? 0) >= (dto.daily_limit_usd ?? 10),
      last_call_at: dto.last_call_at ?? '',
    }
  }

  function upsertSessions(sessions: SessionCostSummaryDto[]) {
    const next = { ...summariesBySession.value }
    for (const session of sessions) {
      next[session.session_id] = normalizeSession(session)
    }
    summariesBySession.value = next
  }

  function pickBestSessionId(preferredSessionId?: string): string | null {
    if (preferredSessionId && summariesBySession.value[preferredSessionId]) {
      return preferredSessionId
    }
    const entries = Object.values(summariesBySession.value)
    if (entries.length === 0) return null
    const sorted = [...entries].sort((a, b) => {
      const ta = new Date(a.last_call_at || 0).getTime()
      const tb = new Date(b.last_call_at || 0).getTime()
      if (tb !== ta) return tb - ta
      return (b.total_calls ?? 0) - (a.total_calls ?? 0)
    })
    return sorted[0]?.session_id ?? null
  }

  let currentRequestId = 0

  async function loadSummary(sessionId?: string) {
    const reqId = ++currentRequestId
    loading.value = true
    error.value = null
    try {
      const data = await fetchCostSummary(sessionId)
      if (reqId !== currentRequestId) return // ignorar respuesta obsoleta
      if (data.status !== 'ok') throw new Error('API returned non-ok status')

      if (data.not_found && sessionId) {
        const fallback = await fetchCostSummary()
        if (
          fallback.status === 'ok' &&
          fallback.sessions &&
          Array.isArray(fallback.sessions)
        ) {
          if (reqId !== currentRequestId) return
          upsertSessions(fallback.sessions)
          currentSessionId.value = pickBestSessionId(sessionId)
        }
      } else if (data.sessions && Array.isArray(data.sessions)) {
        upsertSessions(data.sessions)
        currentSessionId.value = pickBestSessionId(sessionId)
      } else if (data.session_id) {
        const mapped = normalizeSession({
          session_id: data.session_id,
          user_id: data.user_id ?? 'default',
          total_calls: data.total_calls ?? 0,
          total_input_tokens: data.total_input_tokens ?? 0,
          total_output_tokens: data.total_output_tokens ?? 0,
          total_cost_usd: data.total_cost_usd ?? 0,
          daily_limit_usd: data.daily_limit_usd ?? 10,
          remaining_budget_usd: data.remaining_budget_usd ?? 10,
          budget_exceeded: data.budget_exceeded ?? false,
          last_call_at: data.last_call_at ?? '',
        })
        summariesBySession.value = {
          ...summariesBySession.value,
          [data.session_id]: mapped,
        }
        currentSessionId.value = data.session_id
      }
      lastRefresh.value = Date.now()
    } catch (e) {
      if (reqId !== currentRequestId) return
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      if (reqId === currentRequestId) {
        loading.value = false
      }
    }
  }

  function setCurrentSession(sessionId: string) {
    currentSessionId.value = sessionId
  }

  function clearError() {
    error.value = null
  }

  return {
    summariesBySession,
    currentSessionId,
    loading,
    error,
    lastRefresh,
    currentSummary,
    allSessions,
    totalCost,
    budgetPercentageUsed,
    loadSummary,
    setCurrentSession,
    clearError,
  }
})
