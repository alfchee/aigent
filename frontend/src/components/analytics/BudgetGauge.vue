<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<{
    spent: number
    limit: number
    currency?: string
    showLabels?: boolean
  }>(),
  {
    currency: 'USD',
    showLabels: true,
  },
)

const percentage = computed(() => {
  if (props.limit <= 0) return 0
  return Math.min(100, (props.spent / props.limit) * 100)
})

const exceeded = computed(() => props.spent > props.limit)

const remaining = computed(() => Math.max(0, props.limit - props.spent))

const barColor = computed(() => {
  if (exceeded.value) return 'bg-danger'
  if (percentage.value >= 80) return 'bg-warning'
  return 'bg-brand'
})

const formattedSpent = computed(() => {
  return `${props.currency} ${props.spent.toFixed(2)}`
})

const formattedLimit = computed(() => {
  return `${props.currency} ${props.limit.toFixed(2)}`
})

const formattedRemaining = computed(() => {
  return `${props.currency} ${remaining.value.toFixed(2)}`
})
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div v-if="showLabels" class="flex items-center justify-between text-xs text-muted">
      <span>{{ formattedSpent }} / {{ formattedLimit }}</span>
      <span
        :class="
          cn(
            'font-medium',
            exceeded ? 'text-danger' : percentage >= 80 ? 'text-warning' : 'text-muted',
          )
        "
      >
        {{ exceeded ? '¡Límite excedido!' : `${formattedRemaining} restante` }}
      </span>
    </div>
    <div
      class="relative h-2.5 w-full overflow-hidden rounded-full bg-surface2"
      role="progressbar"
      :aria-valuenow="Math.round(percentage)"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div
        :class="cn('h-full rounded-full transition-all duration-500', barColor)"
        :style="{ width: `${percentage}%` }"
      />
    </div>
    <div
      v-if="showLabels"
      class="flex items-center justify-between text-[10px] text-muted/70"
    >
      <span>0%</span>
      <span>50%</span>
      <span>100%</span>
    </div>
  </div>
</template>
