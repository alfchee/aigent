<script setup lang="ts">
import { useChatStore } from '../../stores/chat';
import { Loader2, BrainCircuit } from 'lucide-vue-next';

const store = useChatStore();
</script>

<template>
  <div 
    v-if="store.isStreaming && store.currentThought"
    class="flex items-center gap-3 px-4 py-2 bg-sky-50 border border-sky-100 rounded-full shadow-sm text-sm text-sky-700 animate-in fade-in slide-in-from-bottom-2"
  >
    <div class="relative">
      <BrainCircuit class="w-4 h-4" />
      <span class="absolute -top-1 -right-1 flex h-2 w-2">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
        <span class="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
      </span>
    </div>
    <span class="font-medium truncate max-w-xs md:max-w-md">{{ store.currentThought }}</span>
  </div>
</template>
