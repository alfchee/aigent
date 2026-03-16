<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    modelValue: string
    label: string
    placeholder?: string
    maxlength?: number
  }>(),
  { placeholder: '', maxlength: undefined },
)
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()
</script>

<template>
  <label class="grid gap-2">
    <span class="text-sm text-muted">{{ label }}</span>
    <input
      class="h-10 rounded-xl border border-border bg-surface px-3 text-sm text-text outline-none transition focus-visible:ring-2 focus-visible:ring-brand/40"
      :value="props.modelValue"
      :placeholder="props.placeholder"
      :maxlength="props.maxlength"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
  </label>
</template>
