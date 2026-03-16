<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{ modelValue: boolean; label: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const cls = computed(() =>
  cn(
    'relative inline-flex h-6 w-11 items-center rounded-full border border-border transition',
    props.modelValue ? 'bg-brand/80' : 'bg-surface',
  ),
)

const knob = computed(() =>
  cn(
    'inline-block h-5 w-5 transform rounded-full bg-white transition',
    props.modelValue ? 'translate-x-5' : 'translate-x-1',
  ),
)
</script>

<template>
  <label class="flex items-center justify-between gap-3">
    <span class="text-sm text-text">{{ label }}</span>
    <button
      type="button"
      role="switch"
      :aria-checked="modelValue"
      :class="cls"
      @click="emit('update:modelValue', !modelValue)"
    >
      <span :class="knob" />
    </button>
  </label>
</template>
