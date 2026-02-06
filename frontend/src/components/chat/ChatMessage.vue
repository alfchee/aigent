<script setup lang="ts">
import { computed, ref } from 'vue';
import type { Message, LogEntry } from '../../types/chat';
import { 
  User, 
  Bot, 
  Brain, 
  Globe, 
  Terminal, 
  ChevronDown, 
  ChevronRight, 
  CheckCircle, 
  AlertCircle, 
  Info,
  Loader2
} from 'lucide-vue-next';

const props = defineProps<{
  message: Message;
}>();

const isUser = computed(() => props.message.role === 'user');
const hasSteps = computed(() => props.message.steps && props.message.steps.length > 0);
const isExpanded = ref(false);

function toggleDetails() {
  isExpanded.value = !isExpanded.value;
}

function getStepIcon(type: LogEntry['type'], title: string) {
  if (type === 'thinking') return Brain;
  if (type === 'tool') {
    if (title.toLowerCase().includes('navigat') || title.toLowerCase().includes('search')) {
      return Globe;
    }
    return Terminal;
  }
  if (type === 'success') return CheckCircle;
  if (type === 'error') return AlertCircle;
  return Info;
}

function getStepColor(type: LogEntry['type']) {
  if (type === 'thinking') return 'text-amber-500';
  if (type === 'tool') return 'text-purple-500';
  if (type === 'success') return 'text-green-500';
  if (type === 'error') return 'text-red-500';
  return 'text-blue-500';
}
</script>

<template>
  <div 
    class="flex w-full animate-in fade-in slide-in-from-bottom-2 duration-300 group"
    :class="[isUser ? 'justify-end' : 'justify-start']"
  >
    <div 
      class="flex max-w-[90%] md:max-w-[85%] gap-3"
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

      <!-- Content Container -->
      <div class="flex flex-col gap-2 min-w-0 flex-1">
        
        <!-- Glass Box / Accordion (Only for Assistant) -->
        <div 
          v-if="!isUser && (hasSteps || message.currentThought)" 
          class="bg-slate-50 border border-slate-200 rounded-xl overflow-hidden shadow-sm transition-all duration-300"
        >
          <!-- Accordion Header -->
          <button 
            @click="toggleDetails"
            class="w-full flex items-center justify-between p-3 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <div class="flex items-center gap-2">
              <!-- Animated Status Icon -->
              <div v-if="message.isStreaming && message.currentThought" class="relative flex items-center justify-center w-4 h-4">
                 <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                 <Loader2 class="relative inline-flex w-3 h-3 text-sky-600 animate-spin" />
              </div>
              <Brain v-else class="w-4 h-4 text-slate-400" />
              
              <!-- Status Text -->
              <span v-if="message.isStreaming && message.currentThought" class="text-sky-600 truncate max-w-[200px] md:max-w-[300px]">
                {{ message.currentThought }}
              </span>
              <span v-else>
                {{ hasSteps ? `${message.steps?.length} steps processed` : 'Thinking Process' }}
              </span>
            </div>
            
            <div class="flex items-center text-slate-400">
               <ChevronDown v-if="isExpanded" class="w-4 h-4" />
               <ChevronRight v-else class="w-4 h-4" />
            </div>
          </button>

          <!-- Accordion Body -->
          <div v-if="isExpanded" class="border-t border-slate-200 bg-white">
            <div class="p-3 space-y-3 max-h-[400px] overflow-y-auto custom-scrollbar">
              <div v-for="step in message.steps" :key="step.id" class="flex gap-3 text-xs">
                <div class="flex-shrink-0 mt-0.5">
                  <component :is="getStepIcon(step.type, step.title)" class="w-4 h-4" :class="getStepColor(step.type)" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="font-medium text-slate-700 flex items-center gap-2">
                    {{ step.title }}
                    <span class="text-[10px] text-slate-400 font-normal ml-auto">
                      {{ new Date(step.timestamp).toLocaleTimeString([], {minute:'2-digit', second:'2-digit'}) }}
                    </span>
                  </div>
                  <!-- Tool Arguments or Details -->
                  <div v-if="step.details" class="mt-1 font-mono text-[10px] bg-slate-50 p-2 rounded border border-slate-100 text-slate-600 overflow-x-auto">
                    <pre v-if="typeof step.details === 'object'">{{ JSON.stringify(step.details, null, 2) }}</pre>
                    <div v-else>{{ step.details }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Main Message Bubble -->
        <div 
          v-if="message.content"
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
            <span v-if="message.isStreaming && !message.currentThought" class="inline-block w-2 h-4 ml-1 bg-current animate-pulse align-middle"></span>
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
  background-color: #cbd5e1;
  border-radius: 20px;
}
</style>
