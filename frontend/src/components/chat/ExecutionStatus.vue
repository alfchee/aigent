<script setup lang="ts">
import { computed } from 'vue'
import { Bot, Wrench, AlertTriangle } from 'lucide-vue-next'
import type { ExecutionEvent } from '@/types/chat'

const props = defineProps<{ events: ExecutionEvent[] }>()

const visibleEvents = computed(() => props.events.slice(-3).reverse())

function iconFor(type: ExecutionEvent['type']) {
  if (type === 'tool_call') return Wrench
  if (type === 'error') return AlertTriangle
  return Bot
}

function toneFor(type: ExecutionEvent['type']) {
  if (type === 'error') {
    return 'border-danger/30 bg-danger/10 text-danger'
  }
  if (type === 'tool_call') {
    return 'border-brand/30 bg-brand/10 text-brand'
  }
  return 'border-border bg-surface text-muted'
}
</script>

<template>
  <div class="grid gap-2">
    <div
      v-for="event in visibleEvents"
      :key="event.id"
      class="rounded-lg border px-3 py-2 text-xs"
      :class="toneFor(event.type)"
    >
      <div class="flex items-center gap-2">
        <component :is="iconFor(event.type)" class="h-3.5 w-3.5 shrink-0" />
        <span class="font-medium">{{ event.label }}</span>
        <span class="ml-auto text-[11px] opacity-80">
          {{
            new Date(event.createdAt).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })
          }}
        </span>
      </div>
      <div v-if="event.details" class="mt-1 text-[11px] opacity-90">
        {{ event.details }}
      </div>
    </div>
  </div>
</template>
