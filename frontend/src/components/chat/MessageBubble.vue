<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/types/chat'
import UserAvatar from './UserAvatar.vue'
import IconButton from '@/components/ui/IconButton.vue'
import { Copy, Check, CheckCheck, Clock, AlertTriangle } from 'lucide-vue-next'
import { cn } from '@/lib/utils'
import { renderMarkdownSync, isMultilineMarkdown } from '@/services/markdown'

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
    'max-w-[78ch] whitespace-pre-wrap rounded-xl border px-3.5 py-2.5 text-[13px] leading-[1.2]',
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

const renderedContent = computed(() => {
  if (isUser.value) return null
  if (!isMultilineMarkdown(props.message.text)) return null
  return renderMarkdownSync(props.message.text)
})

async function copy() {
  await navigator.clipboard.writeText(props.message.text)
}
</script>

<template>
  <div :class="cn('flex gap-2.5', isUser ? 'flex-row-reverse' : 'flex-row')">
    <UserAvatar
      :name="isUser ? userName : 'Agente'"
      :kind="isUser ? 'user' : 'assistant'"
    />
    <div class="grid gap-1">
      <div
        class="flex items-center gap-1.5"
        :class="isUser ? 'justify-end' : 'justify-start'"
      >
        <span class="text-[11px] text-muted">{{ time }}</span>
        <component :is="statusIcon" v-if="statusIcon" class="h-3 w-3 text-muted" />
        <IconButton aria-label="Copiar mensaje" size="sm" variant="ghost" @click="copy">
          <Copy class="h-3.5 w-3.5" />
        </IconButton>
      </div>
      <div :class="bubble">
        <div v-if="renderedContent" class="markdown-body" v-html="renderedContent" />
        <span v-else class="whitespace-pre-wrap">{{ message.text }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.markdown-body :deep(h1) {
  margin-top: 10px;
  margin-bottom: 4px;
  line-height: 1.2;
}

.markdown-body :deep(h2) {
  margin-top: 8px;
  margin-bottom: 4px;
  line-height: 1.2;
}

.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin-top: 6px;
  margin-bottom: 2px;
  line-height: 1.2;
}

.markdown-body :deep(p),
.markdown-body :deep(ul),
.markdown-body :deep(ol),
.markdown-body :deep(blockquote) {
  margin-top: 4px;
  margin-bottom: 4px;
  line-height: 1.2;
}

.markdown-body :deep(li) {
  margin-top: 2px;
  margin-bottom: 2px;
  line-height: 1.2;
}

.markdown-body :deep(pre) {
  margin-top: 6px;
  margin-bottom: 6px;
  line-height: 1.2;
}

.markdown-body :deep(hr) {
  margin-top: 8px;
  margin-bottom: 8px;
}
</style>
