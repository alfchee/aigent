<script setup lang="ts">
import { computed } from 'vue'
import {
  CheckCircle,
  AlertCircle,
  RefreshCw,
  AlertTriangle,
  MinusCircle,
} from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    status: 'idle' | 'refining' | 'approved' | 'revised' | 'incomplete' | 'error'
  }>(),
  { status: 'idle' },
)

const config = computed(() => {
  switch (props.status) {
    case 'approved':
      return {
        label: 'Aprobado',
        color: 'text-brand bg-brand/10 border-brand/30',
        icon: CheckCircle,
      }
    case 'revised':
      return {
        label: 'Revisado',
        color: 'text-warning bg-warning/10 border-warning/30',
        icon: RefreshCw,
      }
    case 'incomplete':
      return {
        label: 'Incompleto',
        color: 'text-orange bg-orange/10 border-orange/30',
        icon: AlertCircle,
      }
    case 'error':
      return {
        label: 'Error',
        color: 'text-danger bg-danger/10 border-danger/30',
        icon: AlertTriangle,
      }
    case 'refining':
      return {
        label: 'Refinando…',
        color: 'text-blue bg-blue-500/10 border-blue-500/30',
        icon: RefreshCw,
      }
    default:
      return {
        label: 'Idle',
        color: 'text-muted bg-surface2 border-border',
        icon: MinusCircle,
      }
  }
})
</script>

<template>
  <span
    :class="[
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border',
      config.color,
    ]"
  >
    <component :is="config.icon" class="h-3 w-3" />
    {{ config.label }}
  </span>
</template>
