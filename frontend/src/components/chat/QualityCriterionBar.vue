<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    score?: number
    animated?: boolean
  }>(),
  { score: 0, animated: false },
)

const barColor = computed(() => {
  if (props.score >= 80) return 'bg-brand'
  if (props.score >= 50) return 'bg-warning'
  return 'bg-muted'
})

const width = computed(() => `${Math.min(100, Math.max(0, props.score))}%`)
</script>

<template>
  <div class="flex items-center gap-2">
    <span class="text-[11px] text-muted w-20 shrink-0 truncate">{{ label }}</span>
    <div class="flex-1 h-2 bg-surface2 rounded-full overflow-hidden">
      <div
        :class="[
          'h-full rounded-full transition-all',
          barColor,
          { 'animate-pulse': animated },
        ]"
        :style="{ width }"
      />
    </div>
    <span class="text-[11px] text-muted w-8 text-right tabular-nums">{{ score }}%</span>
  </div>
</template>
