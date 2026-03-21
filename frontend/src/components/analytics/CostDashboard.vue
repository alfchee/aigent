<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { RefreshCw, AlertTriangle } from 'lucide-vue-next'
import { useCostStore } from '@/stores/cost'
import { formatTokens, formatCost } from '@/services/costApi'
import BudgetGauge from './BudgetGauge.vue'
import CostCallList from './CostCallList.vue'

const props = withDefaults(
  defineProps<{
    sessionId?: string
    refreshInterval?: number
  }>(),
  { refreshInterval: 0, sessionId: undefined },
)

const costStore = useCostStore()

const summary = computed(() => costStore.currentSummary)
const allSessions = computed(() => costStore.allSessions)
const activeSessionId = computed(() => costStore.currentSessionId)
const loading = computed(() => costStore.loading)
const error = computed(() => costStore.error)

const hasData = computed(() => summary.value !== null)
const hasMultipleSessions = computed(() => allSessions.value.length > 1)

async function load() {
  const targetSessionId = props.sessionId ?? costStore.currentSessionId ?? undefined
  await costStore.loadSummary(targetSessionId)
}

async function onSelectSession(event: Event) {
  const target = event.target as HTMLSelectElement
  if (!target.value) return
  costStore.setCurrentSession(target.value)
  await costStore.loadSummary(target.value)
}

function clearError() {
  costStore.clearError()
}

onMounted(() => {
  load()
  if (props.refreshInterval > 0) {
    const interval = setInterval(load, props.refreshInterval)
    return () => clearInterval(interval)
  }
})

defineExpose({ load })
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-semibold text-text flex items-center gap-2">
        💰 Cost Dashboard
      </h3>
      <div class="flex items-center gap-2">
        <select
          v-if="hasMultipleSessions"
          class="h-8 rounded-md border border-border bg-surface px-2 text-xs text-text"
          :value="activeSessionId ?? ''"
          @change="onSelectSession"
        >
          <option
            v-for="session in allSessions"
            :key="session.session_id"
            :value="session.session_id"
          >
            {{ session.session_id.slice(0, 8) }} ·
            {{ formatCost(session.total_cost_usd) }}
          </option>
        </select>
        <button
          type="button"
          class="flex items-center gap-1.5 text-xs text-muted hover:text-text disabled:opacity-50 transition"
          :disabled="loading"
          @click="load"
        >
          <RefreshCw :class="['h-3.5 w-3.5', loading ? 'animate-spin' : '']" />
          Refresh
        </button>
      </div>
    </div>

    <div
      v-if="error"
      class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 p-3"
    >
      <AlertTriangle class="h-4 w-4 shrink-0 text-danger mt-0.5" />
      <div class="flex-1">
        <p class="text-xs text-danger font-medium">Error loading costs</p>
        <p class="text-[11px] text-danger/80 mt-0.5">{{ error }}</p>
        <button
          type="button"
          class="mt-2 text-[11px] text-danger underline hover:no-underline"
          @click="clearError"
        >
          Dismiss
        </button>
      </div>
    </div>

    <div v-if="hasData && summary" class="flex flex-col gap-3">
      <div class="rounded-lg border border-border bg-surface2/30 p-2 text-xs text-muted">
        Session: <span class="font-mono text-text">{{ summary.session_id }}</span>
      </div>
      <div class="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
        <div class="rounded-lg border border-border bg-surface2/30 p-2">
          <div class="text-[11px] text-muted">Total Calls</div>
          <div class="text-sm font-semibold tabular-nums">{{ summary.total_calls }}</div>
        </div>
        <div class="rounded-lg border border-border bg-surface2/30 p-2">
          <div class="text-[11px] text-muted">Input Tokens</div>
          <div class="text-sm font-semibold tabular-nums">
            {{ formatTokens(summary.total_input_tokens) }}
          </div>
        </div>
        <div class="rounded-lg border border-border bg-surface2/30 p-2">
          <div class="text-[11px] text-muted">Output Tokens</div>
          <div class="text-sm font-semibold tabular-nums">
            {{ formatTokens(summary.total_output_tokens) }}
          </div>
        </div>
        <div class="rounded-lg border border-border bg-surface2/30 p-2">
          <div class="text-[11px] text-muted">Total Cost</div>
          <div class="text-sm font-semibold tabular-nums">
            {{ formatCost(summary.total_cost_usd) }}
          </div>
        </div>
      </div>

      <div class="rounded-lg border border-border p-3 space-y-2">
        <div class="text-[11px] text-muted font-medium uppercase tracking-wide">
          Budget ({{ summary.daily_limit_usd.toFixed(2) }}
          {{ summary.currency ?? 'USD' }} daily)
        </div>
        <BudgetGauge
          :spent="summary.daily_limit_usd - summary.remaining_budget_usd"
          :limit="summary.daily_limit_usd"
          :currency="summary.currency ?? 'USD'"
        />
        <div
          v-if="summary.budget_exceeded"
          class="flex items-center gap-1.5 text-[11px] text-danger"
        >
          <AlertTriangle class="h-3 w-3" />
          ¡Presupuesto diario excedido!
        </div>
      </div>

      <div class="rounded-lg border border-border p-3">
        <div class="text-[11px] text-muted font-medium uppercase tracking-wide mb-2">
          Última llamada
        </div>
        <div class="text-xs text-muted">
          {{
            summary.last_call_at
              ? new Date(summary.last_call_at).toLocaleString()
              : 'Sin datos'
          }}
        </div>
      </div>

      <CostCallList :calls="[]" :page-size="5" />
    </div>

    <div v-else-if="!loading && !error" class="flex items-center justify-center py-8">
      <div class="flex flex-col items-center gap-2 text-muted">
        <div class="h-8 w-8 rounded-full bg-surface2 animate-pulse" />
        <p class="text-xs">Sin datos de costos disponibles</p>
      </div>
    </div>

    <div v-if="loading && !hasData" class="flex flex-col gap-3">
      <div class="grid grid-cols-3 gap-2">
        <div v-for="i in 3" :key="i" class="h-14 rounded-lg bg-surface2 animate-pulse" />
      </div>
      <div class="h-16 rounded-lg bg-surface2 animate-pulse" />
    </div>
  </div>
</template>
