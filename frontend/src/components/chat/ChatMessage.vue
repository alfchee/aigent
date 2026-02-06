<script setup lang="ts">
import { computed } from 'vue';
import type { Message } from '../../types/chat';
import { User, Bot } from 'lucide-vue-next';

const props = defineProps<{
  message: Message;
}>();

const isUser = computed(() => props.message.role === 'user');
</script>

<template>
  <div 
    class="flex w-full animate-in fade-in slide-in-from-bottom-2 duration-300 group"
    :class="[isUser ? 'justify-end' : 'justify-start']"
  >
    <div 
      class="flex max-w-[85%] gap-3"
      :class="[isUser ? 'flex-row-reverse' : 'flex-row']"
    >
      <!-- Avatar -->
      <div 
        class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm mt-1"
        :class="[isUser ? 'bg-sky-500 text-white' : 'bg-white border border-slate-200 text-sky-500']"
      >
        <User v-if="isUser" class="w-5 h-5" />
        <Bot v-else class="w-5 h-5" />
      </div>

      <!-- Bubble -->
      <div 
        class="p-4 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap"
        :class="[
          isUser 
            ? 'bg-sky-500 text-white rounded-tr-none' 
            : 'bg-white text-slate-800 border border-slate-200 rounded-tl-none'
        ]"
      >
        <div class="flex items-center gap-2 mb-1 pb-1 border-b opacity-80" :class="isUser ? 'border-sky-400' : 'border-slate-100'">
          <span class="text-[10px] font-bold uppercase tracking-widest">{{ isUser ? 'You' : 'Navibot' }}</span>
          <span class="text-[10px] ml-auto">{{ new Date(message.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}</span>
        </div>
        
        <div class="prose prose-sm max-w-none" :class="isUser ? 'prose-invert' : ''">
          {{ message.content }}
          <span v-if="message.isStreaming" class="inline-block w-2 h-4 ml-1 bg-current animate-pulse align-middle"></span>
        </div>
      </div>
    </div>
  </div>
</template>
