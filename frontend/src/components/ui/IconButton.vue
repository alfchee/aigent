<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<{ variant?: 'ghost' | 'secondary' | 'danger'; size?: 'sm' | 'md' }>(),
  { variant: 'ghost', size: 'md' },
)

const attrs = useAttrs()

const cls = computed(() => {
  const base =
    'inline-flex items-center justify-center rounded-xl transition focus-visible:ring-2 focus-visible:ring-brand/40 disabled:opacity-50 disabled:cursor-not-allowed'
  const size = props.size === 'sm' ? 'h-9 w-9' : 'h-10 w-10'
  if (props.variant === 'danger') return cn(base, size, 'hover:bg-danger/10 text-danger')
  if (props.variant === 'secondary')
    return cn(base, size, 'bg-surface border border-border hover:bg-surface2/80')
  return cn(base, size, 'hover:bg-surface2/70')
})
</script>

<template>
  <button type="button" :class="cls" v-bind="attrs">
    <slot />
  </button>
</template>
