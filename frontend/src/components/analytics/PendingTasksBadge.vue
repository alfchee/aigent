<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    tasks: string[]
    expanded?: boolean
  }>(),
  { expanded: false },
)

const emit = defineEmits<{
  (e: 'toggle'): void
}>()

const count = computed(() => props.tasks.length)
</script>

<template>
  <div class="flex flex-col gap-1">
    <button
      type="button"
      class="flex items-center gap-1.5 text-xs text-muted hover:text-text transition-colors"
      :class="{ 'text-warning': count > 0 }"
      @click="emit('toggle')"
    >
      <span
        :class="[
          'inline-flex items-center justify-center h-4 w-4 rounded-full text-[10px] font-bold',
          count > 0 ? 'bg-warning/20 text-warning' : 'bg-surface2 text-muted/60',
        ]"
      >
        {{ count }}
      </span>
      <span class="truncate max-w-[150px]">
        {{ count > 0 ? 'Tareas pendientes' : 'Sin tareas' }}
      </span>
    </button>

    <div v-if="expanded && tasks.length > 0" class="ml-5 flex flex-col gap-0.5">
      <div v-for="(task, i) in tasks" :key="i" class="text-[11px] text-muted/80 truncate">
        · {{ task }}
      </div>
    </div>
  </div>
</template>
