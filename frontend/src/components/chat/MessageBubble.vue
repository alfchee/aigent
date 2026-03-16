<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/types/chat'
import UserAvatar from './UserAvatar.vue'
import IconButton from '@/components/ui/IconButton.vue'
import { Copy, Check, CheckCheck, Clock, AlertTriangle } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

const props = defineProps<{ message: ChatMessage; userName: string }>()

const isUser = computed(() => props.message.role === 'user')
const time = computed(() =>
  new Date(props.message.createdAt).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  }),
)

const bubble = computed(() =>
  cn(
    'max-w-[78ch] whitespace-pre-wrap rounded-xl border px-4 py-3 text-sm leading-6',
    isUser.value
      ? 'bg-brand/10 border-brand/25 text-text'
      : 'bg-surface border-border text-text',
  ),
)

const statusIcon = computed(() => {
  if (props.message.role !== 'user') return null
  if (props.message.status === 'sending') return Clock
  if (props.message.status === 'sent') return Check
  if (props.message.status === 'delivered' || props.message.status === 'read')
    return CheckCheck
  if (props.message.status === 'error') return AlertTriangle
  return null
})

async function copy() {
  await navigator.clipboard.writeText(props.message.text)
}
</script>

<template>
  <div :class="cn('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')">
    <UserAvatar
      :name="isUser ? userName : 'Agente'"
      :kind="isUser ? 'user' : 'assistant'"
    />
    <div class="grid gap-1">
      <div
        class="flex items-center gap-2"
        :class="isUser ? 'justify-end' : 'justify-start'"
      >
        <span class="text-xs text-muted">{{ time }}</span>
        <component :is="statusIcon" v-if="statusIcon" class="h-3.5 w-3.5 text-muted" />
        <IconButton aria-label="Copiar mensaje" size="sm" variant="ghost" @click="copy">
          <Copy class="h-4 w-4" />
        </IconButton>
      </div>
      <div :class="bubble">
        {{ message.text }}
      </div>
    </div>
  </div>
</template>
