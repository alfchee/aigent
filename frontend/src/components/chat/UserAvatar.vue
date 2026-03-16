<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = withDefaults(defineProps<{ name: string; kind?: 'user' | 'assistant' }>(), {
  kind: 'assistant',
})

const initials = computed(() => {
  const s = props.name.trim()
  if (!s) return '?'
  const parts = s.split(/\s+/).slice(0, 2)
  return parts.map((p) => p[0]?.toUpperCase()).join('')
})

const cls = computed(() =>
  cn(
    'flex h-9 w-9 items-center justify-center rounded-xl border border-border text-xs font-semibold',
    props.kind === 'user' ? 'bg-brand/15 text-brand' : 'bg-surface2/60 text-text',
  ),
)
</script>

<template>
  <div :class="cls" :aria-label="name" role="img">
    {{ initials }}
  </div>
</template>
