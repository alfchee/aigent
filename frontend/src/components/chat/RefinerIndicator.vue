<script setup lang="ts">
import { computed } from 'vue'
import { Search } from 'lucide-vue-next'
import { useWebSocketStore } from '@/stores/websocket'
import { useUserConfigStore } from '@/stores/userConfig'
import QualityCriterionBar from './QualityCriterionBar.vue'
import RefinerStatusBadge from './RefinerStatusBadge.vue'

const props = withDefaults(
  defineProps<{
    sessionId?: string
  }>(),
  { sessionId: undefined },
)

const wsStore = useWebSocketStore()
const userStore = useUserConfigStore()

const sessionId = computed(() => props.sessionId ?? userStore.sessionId)

const refineStatus = computed(() => {
  const state = wsStore.getAgentState(sessionId.value)
  return state?.refine_status ?? null
})

const isRefining = computed(() => refineStatus.value?.stage === 'refining')

const isVisible = computed(() => {
  const stage = refineStatus.value?.stage
  return stage && stage !== 'idle'
})

const criteria = computed(() => {
  const c = refineStatus.value?.criteria
  if (!c || c.length === 0) return ['relevance', 'completeness', 'accuracy', 'clarity']
  return c
})

const mockScores: Record<string, number> = {
  relevance: 85,
  completeness: 72,
  accuracy: 90,
  clarity: 78,
}

const scores = computed(() => {
  if (refineStatus.value?.stage === 'approved')
    return criteria.value.map((c) => ({ label: c, score: 95 }))
  if (refineStatus.value?.stage === 'incomplete')
    return criteria.value.map((c) => ({ label: c, score: 40 }))
  return criteria.value.map((c) => ({ label: c, score: mockScores[c] ?? 75 }))
})
</script>

<template>
  <div
    v-if="isVisible"
    class="rounded-lg border border-border bg-surface px-3 py-2 flex flex-col gap-2"
  >
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2 text-xs">
        <Search
          class="h-3.5 w-3.5 text-brand shrink-0"
          :class="{ 'animate-pulse': isRefining }"
        />
        <span class="font-medium">
          {{ isRefining ? 'Refinando respuesta…' : 'Refinamiento completado' }}
        </span>
      </div>
      <RefinerStatusBadge :status="refineStatus?.stage ?? 'idle'" />
    </div>

    <div v-if="!isRefining && scores.length > 0" class="flex flex-col gap-1.5">
      <QualityCriterionBar
        v-for="c in scores"
        :key="c.label"
        :label="c.label"
        :score="c.score"
      />
    </div>

    <div v-if="refineStatus?.result && !isRefining" class="text-[11px] text-muted">
      {{ refineStatus.result }}
    </div>
  </div>
</template>
