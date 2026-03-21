<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'
import type { LLMCallRecordDto } from '@/services/costApi'
import { formatTokens, formatCost } from '@/services/costApi'

const props = withDefaults(
  defineProps<{
    calls: LLMCallRecordDto[]
    pageSize?: number
  }>(),
  { pageSize: 10 },
)

const visibleCalls = computed(() => props.calls.slice(0, props.pageSize))

const maxCost = computed(() => {
  if (props.calls.length === 0) return 1
  return Math.max(...props.calls.map((c) => c.cost_usd))
})

function barWidth(costUsd: number): string {
  const pct = (costUsd / maxCost.value) * 100
  return `${Math.max(2, pct)}%`
}

function providerColor(provider: string): string {
  const p = provider.toLowerCase()
  if (p.includes('gemini')) return 'bg-purple-500'
  if (p.includes('openai') || p.includes('gpt')) return 'bg-green-500'
  if (p.includes('anthropic') || p.includes('claude')) return 'bg-orange-500'
  return 'bg-brand'
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div
      v-for="call in visibleCalls"
      :key="call.timestamp"
      class="flex items-center gap-2 text-xs"
    >
      <div class="w-16 truncate text-muted" :title="call.provider">
        {{ call.provider }}
      </div>
      <div class="h-4 flex-1 min-w-0">
        <div
          :class="cn('h-full rounded-sm transition-all', providerColor(call.provider))"
          :style="{ width: barWidth(call.cost_usd) }"
        />
      </div>
      <div class="w-16 text-right font-mono text-muted">
        {{ formatCost(call.cost_usd) }}
      </div>
      <div class="w-12 text-right text-muted/70">
        {{ formatTokens(call.input_tokens + call.output_tokens) }}
      </div>
    </div>
    <div v-if="calls.length === 0" class="py-4 text-center text-xs text-muted">
      Sin llamadas registradas
    </div>
  </div>
</template>
