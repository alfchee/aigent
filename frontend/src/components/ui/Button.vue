<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'sm' | 'md'
  }>(),
  { variant: 'secondary', size: 'md' },
)

const base =
  'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition focus-visible:ring-2 focus-visible:ring-brand/40 focus-visible:ring-offset-0 disabled:opacity-50 disabled:cursor-not-allowed'

const cls = computed(() => {
  const size = props.size === 'sm' ? 'h-9 px-3 text-sm' : 'h-10 px-4 text-sm'
  const v = props.variant
  if (v === 'primary') return cn(base, size, 'bg-brand text-white hover:bg-brand2')
  if (v === 'danger') return cn(base, size, 'bg-danger text-white hover:bg-danger/90')
  if (v === 'ghost')
    return cn(base, size, 'bg-transparent text-text hover:bg-surface2/70')
  return cn(base, size, 'bg-surface text-text border border-border hover:bg-surface2/80')
})
</script>

<template>
  <button type="button" :class="cls">
    <slot />
  </button>
</template>
