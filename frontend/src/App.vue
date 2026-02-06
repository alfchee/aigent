<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue';
import { useChatStore } from './stores/chat';
import ChatMessage from './components/chat/ChatMessage.vue';
import ChatInput from './components/chat/ChatInput.vue';
import ConsoleLog from './components/chat/ConsoleLog.vue';
import StreamStatus from './components/chat/StreamStatus.vue';
import { PanelRightOpen, PanelRightClose } from 'lucide-vue-next';

const store = useChatStore();
const chatContainer = ref<HTMLElement | null>(null);
const showConsole = ref(true);

function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
  }
}

// Auto-scroll on new messages
watch(() => store.messages.length, () => {
  nextTick(scrollToBottom);
});

// Auto-scroll on content update (streaming)
watch(() => store.messages[store.messages.length - 1]?.content, () => {
  // Only scroll if we were already near bottom or it's a new message
  if (chatContainer.value) {
    const { scrollTop, scrollHeight, clientHeight } = chatContainer.value;
    if (scrollHeight - scrollTop - clientHeight < 100) {
      chatContainer.value.scrollTop = scrollHeight;
    }
  }
});
</script>

<template>
  <div class="h-screen w-screen flex flex-col bg-slate-50 text-slate-900 font-sans overflow-hidden">
    <!-- Header -->
    <header class="h-14 px-4 bg-white border-b border-slate-200 flex justify-between items-center shadow-sm z-10">
      <div class="flex items-center gap-3">
        <div class="bg-sky-500 p-1.5 rounded-lg text-white">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
          </svg>
        </div>
        <h1 class="text-lg font-bold tracking-tight">Navibot <span class="text-sky-500 font-medium font-mono text-xs border border-sky-100 bg-sky-50 px-1.5 py-0.5 rounded ml-1">v2.0</span></h1>
      </div>
      
      <button 
        @click="showConsole = !showConsole"
        class="p-2 text-slate-500 hover:text-sky-600 hover:bg-slate-100 rounded-lg transition-colors"
        title="Toggle System Console"
      >
        <PanelRightClose v-if="showConsole" class="w-5 h-5" />
        <PanelRightOpen v-else class="w-5 h-5" />
      </button>
    </header>

    <!-- Main Content Split -->
    <div class="flex-1 flex overflow-hidden">
      
      <!-- Left: Chat Area -->
      <main class="flex-1 flex flex-col relative min-w-0">
        <!-- Messages -->
        <div 
          ref="chatContainer"
          class="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-fixed"
        >
          <ChatMessage 
            v-for="msg in store.messages" 
            :key="msg.id" 
            :message="msg" 
          />
        </div>

        <!-- Floating Status Indicator -->
        <div class="absolute bottom-24 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
          <StreamStatus />
        </div>

        <!-- Input Area -->
        <ChatInput class="z-30" />
      </main>

      <!-- Right: Console/Observability -->
      <aside 
        class="border-l border-slate-200 bg-slate-50 transition-all duration-300 ease-in-out flex flex-col"
        :class="[showConsole ? 'w-80 md:w-96 translate-x-0' : 'w-0 translate-x-full border-none']"
      >
        <div class="h-full p-2 overflow-hidden" v-show="showConsole">
          <ConsoleLog />
        </div>
      </aside>
    </div>
  </div>
</template>
