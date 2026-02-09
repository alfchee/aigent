<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import { useChatStore } from '../../stores/chat'
import { useArtifactsStore } from '../../stores/artifacts'
import ChatMessage from './ChatMessage.vue'

const chat = useChatStore()
const artifacts = useArtifactsStore()
const newMessage = ref('')

const messages = computed(() => chat.messages)
const isLoading = computed(() => chat.isLoading)
const isHistoryLoading = computed(() => chat.isHistoryLoading)
const historyHasMore = computed(() => chat.historyHasMore)
const historyError = computed(() => chat.historyError)

const scrollRef = ref<HTMLElement | null>(null)

async function send() {
  const msg = newMessage.value
  newMessage.value = ''
  await chat.sendMessage(msg, artifacts.sessionId)
}

async function loadMore() {
  await chat.loadMoreHistory(artifacts.sessionId)
}

watch(
  () => chat.messages.length,
  async () => {
    await nextTick()
    scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight })
  }
)
</script>

<template>
  <div class="h-full flex flex-col bg-slate-50 overflow-hidden">
    <div ref="scrollRef" class="flex-1 min-h-0 overflow-y-auto p-4 md:p-8 flex flex-col items-center bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-fixed">
      <div class="w-full max-w-3xl space-y-6">
        <div class="flex items-center justify-center">
          <button
            v-if="historyHasMore"
            type="button"
            class="text-xs px-3 py-2 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-50"
            :disabled="isHistoryLoading"
            @click="loadMore"
          >
            {{ isHistoryLoading ? 'Cargando…' : 'Cargar mensajes anteriores' }}
          </button>
          <div v-else-if="isHistoryLoading" class="text-xs text-slate-500">Cargando…</div>
        </div>
        <div v-if="historyError" class="text-xs text-red-600 text-center">
          Error al cargar historial: {{ historyError }}
        </div>
        <div
          v-for="(msg, index) in messages"
          :key="msg.id ?? index"
          :class="['flex w-full animate-in fade-in slide-in-from-bottom-2 duration-300', msg.role === 'user' ? 'justify-end' : 'justify-start']"
        >
          <ChatMessage :role="msg.role" :content="msg.content" />
        </div>

        <div v-if="isLoading" class="flex justify-start animate-pulse">
          <div class="bg-white p-4 rounded-2xl border border-slate-100 shadow-md flex items-center gap-3">
            <div class="flex gap-1">
              <span class="w-2 h-2 bg-sky-400 rounded-full animate-bounce"></span>
              <span class="w-2 h-2 bg-sky-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
              <span class="w-2 h-2 bg-sky-400 rounded-full animate-bounce [animation-delay:0.4s]"></span>
            </div>
            <span class="text-xs text-slate-500 font-medium">Pensando...</span>
          </div>
        </div>
      </div>
    </div>

    <footer class="p-4 bg-white border-t border-slate-200">
      <div class="max-w-3xl mx-auto">
        <form @submit.prevent="send" class="flex gap-2 relative">
          <textarea
            v-model="newMessage"
            placeholder="Escribe un mensaje..."
            rows="1"
            class="flex-1 p-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all resize-none text-sm pr-12"
            :disabled="isLoading"
            @keydown.enter.prevent="send"
          ></textarea>
          <button
            type="submit"
            :disabled="isLoading || !newMessage.trim()"
            class="absolute right-2 bottom-2 p-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50 disabled:bg-slate-300 transition-colors shadow-sm"
            aria-label="Enviar mensaje"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </form>
        <p class="text-[10px] text-center text-slate-400 mt-2">© 2026 Navibot Agent</p>
      </div>
    </footer>
  </div>
</template>
