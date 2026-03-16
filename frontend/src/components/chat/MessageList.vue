<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { ChatMessage } from '@/types/chat'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import MessageBubble from './MessageBubble.vue'
import TypingIndicator from './TypingIndicator.vue'
import { useMessagesStore } from '@/stores/messages'
import { useUserConfigStore } from '@/stores/userConfig'

const props = defineProps<{ conversationId: string }>()

const store = useMessagesStore()
const user = useUserConfigStore()

const wrap = ref<HTMLDivElement | null>(null)
const atBottom = ref(true)

const items = computed(() => store.messagesByConversationId[props.conversationId] ?? [])
const typing = computed(
  () => store.assistantTypingByConversationId[props.conversationId] ?? false,
)

function onScroll() {
  if (!wrap.value) return
  const el = wrap.value
  atBottom.value = el.scrollTop + el.clientHeight >= el.scrollHeight - 24
  if (el.scrollTop < 80) store.loadMore(props.conversationId).catch(() => {})
}

function scrollToBottom() {
  if (!wrap.value) return
  wrap.value.scrollTop = wrap.value.scrollHeight
}

onMounted(() => {
  scrollToBottom()
})

defineExpose({ scrollToBottom })
</script>

<template>
  <div
    ref="wrap"
    data-testid="message-list-scroll"
    class="h-full min-h-0 overflow-y-auto overflow-x-hidden"
    @scroll="onScroll"
  >
    <div class="px-4 py-5">
      <DynamicScroller :items="items" :min-item-size="72" key-field="id">
        <template #default="{ item, index, active }">
          <DynamicScrollerItem
            :item="item"
            :active="active"
            :data-index="index"
            class="mb-4"
          >
            <MessageBubble :message="item as ChatMessage" :user-name="user.displayName" />
          </DynamicScrollerItem>
        </template>
      </DynamicScroller>

      <div v-if="typing" class="mt-4">
        <TypingIndicator />
      </div>

      <div v-if="store.loadingMore" class="mt-4 text-center text-xs text-muted">
        Cargando…
      </div>
    </div>
  </div>
</template>
