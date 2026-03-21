<script setup lang="ts">
import { computed } from 'vue'
import type { WorkerStatusInfo } from '@/types/chat'

const props = withDefaults(
  defineProps<{
    worker: WorkerStatusInfo
    showDetails?: boolean
  }>(),
  { showDetails: false },
)

const statusColor = computed(() => {
  const s = props.worker.status
  if (s === 'working') return 'bg-brand animate-pulse'
  if (s === 'error') return 'bg-danger'
  return 'bg-muted/40'
})

const statusLabel = computed(() => {
  const s = props.worker.status
  if (s === 'working') return 'Trabajando'
  if (s === 'error') return 'Error'
  return 'Idle'
})

const progressWidth = computed(() => {
  if (props.worker.status !== 'working') return '0%'
  return '80%'
})
</script>

<template>
  <div class="flex items-center gap-2">
    <div class="w-2 h-2 rounded-full shrink-0" :class="statusColor" />
    <span class="text-xs font-medium truncate min-w-0">{{ worker.name }}</span>
    <div
      v-if="worker.status === 'working' && worker.current_task"
      class="flex-1 min-w-0 h-1.5 bg-surface2 rounded-full overflow-hidden"
    >
      <div
        class="h-full bg-brand rounded-full transition-all duration-500"
        :style="{ width: progressWidth }"
      />
    </div>
    <span
      v-if="worker.status === 'working' && worker.current_task && showDetails"
      class="text-[10px] text-muted truncate hidden sm:inline"
    >
      {{ worker.current_task }}
    </span>
    <span v-else-if="worker.status !== 'idle'" class="text-[10px] text-muted">
      {{ statusLabel }}
    </span>
    <span v-else class="text-[10px] text-muted/60"> idle </span>
  </div>
</template>
