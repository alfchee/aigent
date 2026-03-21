<script setup lang="ts">
import { computed } from 'vue'
import { Check, DollarSign, Code, Search, Share2 } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    ruleType: 'financial' | 'social' | 'coding' | 'research'
    description: string
    isActive: boolean
  }>(),
  { isActive: true },
)

const config = computed(() => {
  switch (props.ruleType) {
    case 'financial':
      return {
        icon: DollarSign,
        color: 'text-green bg-green/10 border-green/30',
        label: 'Financiero',
      }
    case 'social':
      return {
        icon: Share2,
        color: 'text-purple bg-purple/10 border-purple/30',
        label: 'Social',
      }
    case 'coding':
      return {
        icon: Code,
        color: 'text-orange bg-orange/10 border-orange/30',
        label: 'Código',
      }
    case 'research':
      return {
        icon: Search,
        color: 'text-blue bg-blue/10 border-blue/30',
        label: 'Investigación',
      }
    default:
      return {
        icon: DollarSign,
        color: 'text-muted bg-surface2 border-border',
        label: props.ruleType,
      }
  }
})
</script>

<template>
  <span
    :class="[
      'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors',
      isActive ? config.color : 'text-muted bg-surface2 border-border',
    ]"
  >
    <component :is="config.icon" class="h-3 w-3 shrink-0" />
    <span>{{ config.label }}</span>
    <Check v-if="isActive" class="h-3 w-3 shrink-0" />
  </span>
</template>
