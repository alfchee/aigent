<script setup lang="ts">
import { ref } from 'vue';
import { useChatStore } from '../../stores/chat';
import { Send, Square, Activity } from 'lucide-vue-next';

const store = useChatStore();
const input = ref('');

function handleSubmit() {
  if (store.isStreaming) {
    store.stopGeneration();
    return;
  }
  if (!input.value.trim()) return;
  store.sendMessage(input.value);
  input.value = '';
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSubmit();
  }
}
</script>

<template>
  <div class="relative bg-white border-t border-slate-200 p-4 shadow-lg">
    <!-- Activity Indicator -->
    <div v-if="store.isStreaming" class="max-w-4xl mx-auto mb-2 flex items-center gap-2 text-xs text-sky-600 animate-pulse">
      <Activity class="w-3 h-3" />
      <span class="font-medium">{{ store.currentThought || 'Processing...' }}</span>
    </div>

    <div class="max-w-4xl mx-auto relative">
      <form @submit.prevent="handleSubmit" class="relative">
        <textarea
          v-model="input"
          @keydown="handleKeydown"
          placeholder="Enter your command or request..."
          rows="1"
          class="w-full pl-4 pr-12 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all resize-none text-sm shadow-inner"
          :disabled="store.isStreaming"
        ></textarea>
        
        <button
          type="submit"
          :disabled="!store.isStreaming && !input.trim()"
          class="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg transition-colors shadow-sm"
          :class="[
            store.isStreaming 
              ? 'text-white bg-red-500 hover:bg-red-600' 
              : !input.trim() 
                ? 'text-slate-400 bg-transparent cursor-not-allowed shadow-none' 
                : 'text-white bg-sky-500 hover:bg-sky-600'
          ]"
        >
          <Square v-if="store.isStreaming" class="w-5 h-5 fill-current" />
          <Send v-else class="w-5 h-5" />
        </button>
      </form>
      <p class="text-[10px] text-center text-slate-400 mt-2">
        Navibot v2.0 &middot; Powered by Gemini 2.0 Flash
      </p>
    </div>
  </div>
</template>
