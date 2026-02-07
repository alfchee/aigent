<script setup lang="ts">
import { computed, ref } from 'vue';
import MarkdownIt from 'markdown-it';
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

const md = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true
});

const isUser = computed(() => props.message.role === 'user');
const hasSteps = computed(() => props.message.steps && props.message.steps.length > 0);
const isExpanded = ref(false);

const renderedContent = computed(() => {
  if (!props.message.content) return '';
  
  let content = props.message.content;

  // Process File Artifacts: [FILE_ARTIFACT: path]
  // We'll replace it with a placeholder HTML that we can style
  // Note: Since we render this inside v-html, we can inject HTML structure
  content = content.replace(
    /\[FILE_ARTIFACT:\s*(.+?)\]/g, 
    (_, path) => {
      // Resolve full URL if it's a relative path starting with /files
      // Assuming backend is at localhost:8231 for now (or same host if proxied)
      // Ideally this comes from env var. For now hardcode or relative logic.
      let fullPath = path;
      if (path.startsWith('/files/')) {
         fullPath = `http://localhost:8231${path}`;
      }

      // Check if it's an image
      const isImage = /\.(png|jpg|jpeg|gif|webp)$/i.test(path);
      
      if (isImage) {
        // Render inline image with a link to open full size
        return `
          <div class="my-3">
            <a href="${fullPath}" target="_blank" class="block relative group cursor-zoom-in">
              <img src="${fullPath}" alt="Generated Image" class="rounded-lg border border-slate-200 shadow-sm max-w-full h-auto transition-transform hover:scale-[1.01]" />
              <div class="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100">
                <span class="bg-white/90 text-slate-700 text-xs px-2 py-1 rounded shadow">Click to open</span>
              </div>
            </a>
          </div>
        `;
      } else {
        // Render standard file card
        return `
          <div class="file-card-container group">
            <div class="icon-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-file"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4h4"/></svg>
            </div>
            <div class="info-wrapper">
              <div class="filename">${path.split('/').pop()}</div>
              <div class="filepath">${path}</div>
            </div>
            <a href="${fullPath}" target="_blank" class="download-wrapper" title="Download / Open">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-download"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
            </a>
          </div>
        `;
      }
    }
  );

  // Wrap standalone base64 images in markdown image syntax if needed
  // This handles cases where the model outputs just the data URI
  if (content.trim().startsWith('data:image/')) {
    content = `![](${content.trim()})`;
  }

  return md.render(content);
});

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

function isBase64Image(data: any): boolean {
  return typeof data === 'string' && data.startsWith('data:image/');
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
                    <!-- Check for Base64 Image -->
                    <div v-if="isBase64Image(step.details)">
                      <img :src="step.details as string" class="max-w-full h-auto rounded border border-slate-200" alt="Tool Screenshot" />
                    </div>
                    <pre v-else-if="typeof step.details === 'object'">{{ JSON.stringify(step.details, null, 2) }}</pre>
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
          class="p-4 rounded-2xl shadow-sm text-sm leading-relaxed"
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
          
          <div 
            class="prose prose-sm max-w-none break-words" 
            :class="isUser ? 'prose-invert' : ''"
            v-html="renderedContent"
          >
          </div>
          <span v-if="message.isStreaming && !message.currentThought" class="inline-block w-2 h-4 ml-1 bg-current animate-pulse align-middle"></span>
        </div>

      </div>
    </div>
  </div>
</template>

<style>
/* Global styles for injected HTML content */
.file-card-container {
  @apply flex items-center gap-3 p-3 my-2 bg-slate-50 border border-slate-200 rounded-lg max-w-sm transition-colors cursor-default select-none;
}
.file-card-container:hover {
  @apply bg-slate-100;
}
.file-card-container .icon-wrapper {
  @apply w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600;
}
.file-card-container .info-wrapper {
  @apply flex-1 min-w-0;
}
.file-card-container .filename {
  @apply text-sm font-medium text-slate-700 truncate;
}
.file-card-container .filepath {
  @apply text-xs text-slate-500 truncate;
}
.file-card-container .download-wrapper {
  @apply w-8 h-8 rounded-full flex items-center justify-center text-slate-400 transition-all;
}
.file-card-container:hover .download-wrapper {
  @apply text-blue-600 bg-blue-50;
}

/* Ensure images in prose are constrained */
.prose img {
  @apply rounded-lg border border-slate-200 shadow-sm max-w-full h-auto;
}
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
