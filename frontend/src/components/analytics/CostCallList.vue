<script setup lang="ts">
import { ref, computed } from 'vue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import type { LLMCallRecordDto } from '@/services/costApi'
import { formatTokens, formatCost, formatRelativeTime } from '@/services/costApi'

const props = withDefaults(
  defineProps<{
    calls: LLMCallRecordDto[]
    pageSize?: number
  }>(),
  { pageSize: 10 },
)

const expandedCallId = ref<string | null>(null)
const page = ref(1)

const totalPages = computed(() => Math.ceil(props.calls.length / props.pageSize))
const paginatedCalls = computed(() => {
  const start = 0
  const end = page.value * props.pageSize
  return props.calls.slice(start, end)
})

function toggleExpand(timestamp: string) {
  expandedCallId.value = expandedCallId.value === timestamp ? null : timestamp
}

function nextPage() {
  if (page.value < totalPages.value) page.value++
}

function prevPage() {
  if (page.value > 1) page.value--
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div
      v-for="call in paginatedCalls"
      :key="call.timestamp"
      class="rounded-lg border border-border bg-surface2/30 overflow-hidden"
    >
      <button
        type="button"
        class="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-surface2/50 transition"
        @click="toggleExpand(call.timestamp)"
      >
        <span class="text-[11px] text-muted font-mono shrink-0">
          {{ formatRelativeTime(call.timestamp) }}
        </span>
        <span class="text-xs font-medium truncate">{{ call.model }}</span>
        <span
          :class="[
            'ml-auto shrink-0 text-[10px] px-1.5 py-0.5 rounded',
            call.cached ? 'bg-brand/20 text-brand' : 'bg-surface2 text-muted',
          ]"
        >
          {{ call.cached ? 'cached' : formatCost(call.cost_usd) }}
        </span>
        <component
          :is="expandedCallId === call.timestamp ? ChevronUp : ChevronDown"
          class="h-3.5 w-3.5 shrink-0 text-muted"
        />
      </button>
      <div
        v-if="expandedCallId === call.timestamp"
        class="px-3 pb-3 pt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]"
      >
        <div>
          <span class="text-muted">Provider:</span>
          <span class="ml-1 font-medium">{{ call.provider }}</span>
        </div>
        <div>
          <span class="text-muted">Tokens in:</span>
          <span class="ml-1 font-mono">{{ formatTokens(call.input_tokens) }}</span>
        </div>
        <div>
          <span class="text-muted">Tokens out:</span>
          <span class="ml-1 font-mono">{{ formatTokens(call.output_tokens) }}</span>
        </div>
        <div>
          <span class="text-muted">Session:</span>
          <span class="ml-1 font-mono text-[10px]"
            >{{ call.session_id.slice(0, 8) }}…</span
          >
        </div>
      </div>
    </div>

    <div v-if="calls.length === 0" class="py-4 text-center text-xs text-muted">
      Sin llamadas registradas
    </div>

    <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 pt-1">
      <button
        type="button"
        class="text-xs text-muted hover:text-text disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="page <= 1"
        @click="prevPage"
      >
        Anterior
      </button>
      <span class="text-[11px] text-muted"> {{ page }} / {{ totalPages }} </span>
      <button
        type="button"
        class="text-xs text-muted hover:text-text disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="page >= totalPages"
        @click="nextPage"
      >
        Siguiente
      </button>
    </div>
  </div>
</template>
