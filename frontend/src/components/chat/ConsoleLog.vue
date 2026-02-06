<script setup lang="ts">
import { ref } from 'vue';
import { useChatStore } from '../../stores/chat';
import { Terminal, ChevronDown, ChevronRight, Info, Brain, Wrench, CheckCircle, AlertCircle, Clock } from 'lucide-vue-next';

const store = useChatStore();

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function toggleLog(id: string) {
  const log = store.logs.find(l => l.id === id);
  if (log) log.expanded = !log.expanded;
}

const getIcon = (type: string) => {
  switch (type) {
    case 'thinking': return Brain;
    case 'tool': return Wrench;
    case 'success': return CheckCircle;
    case 'error': return AlertCircle;
    default: return Info;
  }
};

const getColor = (type: string) => {
  switch (type) {
    case 'thinking': return 'text-purple-400';
    case 'tool': return 'text-amber-400';
    case 'success': return 'text-emerald-400';
    case 'error': return 'text-red-400';
    default: return 'text-blue-400';
  }
};
</script>

<template>
  <div class="h-full flex flex-col bg-slate-900 text-slate-300 font-mono text-xs overflow-hidden rounded-xl border border-slate-800 shadow-inner">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-3 bg-slate-950 border-b border-slate-800">
      <Terminal class="w-4 h-4 text-slate-400" />
      <span class="font-semibold text-slate-200">System Trace</span>
      <span class="ml-auto text-[10px] text-slate-500" v-if="store.isStreaming">LIVE</span>
    </div>

    <!-- Log List -->
    <div class="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
      <div v-if="store.logs.length === 0" class="text-center py-8 text-slate-600 italic">
        No activity recorded yet.
      </div>
      
      <div 
        v-for="log in store.logs" 
        :key="log.id"
        class="rounded border border-transparent hover:border-slate-800 transition-colors"
      >
        <!-- Log Header -->
        <div 
          class="flex items-start gap-2 p-2 cursor-pointer hover:bg-white/5 rounded select-none"
          @click="toggleLog(log.id)"
        >
          <component :is="getIcon(log.type)" class="w-3.5 h-3.5 mt-0.5 flex-shrink-0" :class="getColor(log.type)" />
          
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-slate-200 truncate">{{ log.title }}</span>
              <span class="text-[10px] text-slate-600 ml-auto whitespace-nowrap">{{ formatTime(log.timestamp) }}</span>
            </div>
            
            <!-- Inline Details Preview (if collapsed) -->
            <div v-if="!log.expanded && log.details" class="truncate text-slate-500 mt-0.5">
              {{ typeof log.details === 'string' ? log.details : JSON.stringify(log.details) }}
            </div>
          </div>

          <component 
            v-if="log.details"
            :is="log.expanded ? ChevronDown : ChevronRight" 
            class="w-3 h-3 text-slate-600 mt-0.5" 
          />
        </div>

        <!-- Log Details (Expanded) -->
        <div v-if="log.expanded && log.details" class="pl-7 pr-2 pb-2">
          <div class="bg-black/30 rounded p-2 overflow-x-auto border border-white/5">
            <pre class="text-[10px] text-slate-400 whitespace-pre-wrap">{{ typeof log.details === 'string' ? log.details : JSON.stringify(log.details, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #475569;
}
</style>
