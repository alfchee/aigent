<script setup lang="ts">
import { computed } from 'vue'
import { md } from '../../lib/markdown'

const props = defineProps<{
  role: 'user' | 'assistant'
  content: string
}>()

type Segment = {
  type: 'text' | 'tool_call' | 'tool_result'
  content: string
}

const segments = computed(() => {
  const regex = /(\[tool_call\][\s\S]*?\[\/tool_call\]|\[tool_result\][\s\S]*?\[\/tool_result\])/g
  const parts = props.content.split(regex)
  
  return parts.reduce<Segment[]>((acc, part) => {
    if (!part) return acc
    
    if (part.startsWith('[tool_call]')) {
      const content = part.replace('[tool_call]', '').replace('[/tool_call]', '').trim()
      acc.push({ type: 'tool_call', content })
    } else if (part.startsWith('[tool_result]')) {
      const content = part.replace('[tool_result]', '').replace('[/tool_result]', '').trim()
      acc.push({ type: 'tool_result', content })
    } else {
      if (part.trim()) {
        acc.push({ type: 'text', content: part })
      }
    }
    return acc
  }, [])
})

function getToolName(content: string): string {
  try {
    const json = JSON.parse(content)
    if (json.name) return json.name
    if (json.tool_name) return json.tool_name
    return 'Herramienta'
  } catch {
    return 'Herramienta'
  }
}
</script>

<template>
  <div
    :class="[
      'max-w-[85%] p-4 rounded-2xl shadow-md text-sm leading-relaxed overflow-hidden',
      role === 'user'
        ? 'bg-sky-600 text-white rounded-tr-none'
        : 'bg-white text-slate-800 border border-slate-100 rounded-tl-none'
    ]"
  >
    <div class="flex gap-2 items-center mb-1 pb-1 border-b border-white/10" :class="role === 'user' ? 'border-sky-400' : 'border-slate-100'">
      <span class="text-[10px] font-bold uppercase tracking-widest opacity-70">{{ role === 'user' ? 'Tú' : 'Navibot' }}</span>
    </div>
    
    <div class="space-y-2">
      <template v-for="(segment, idx) in segments" :key="idx">
        <div v-if="segment.type === 'text'" 
             class="prose prose-sm max-w-none break-words"
             :class="role === 'user' ? 'prose-invert' : ''"
             v-html="md.render(segment.content)">
        </div>
        
        <div v-else-if="segment.type === 'tool_call'" class="my-2 border rounded-md overflow-hidden bg-slate-50 border-slate-200 w-full" data-testid="tool-call">
          <details class="group tool-details">
            <summary class="px-3 py-2 text-xs font-mono font-medium text-slate-600 cursor-pointer hover:bg-slate-100 flex items-center gap-2 select-none">
              <span class="text-amber-600">⚡</span> Ejecutar: {{ getToolName(segment.content) }}
            </summary>
            <div class="p-3 border-t border-slate-200 bg-slate-900 text-slate-50 text-xs font-mono overflow-x-auto tool-content">
              <pre>{{ segment.content }}</pre>
            </div>
          </details>
        </div>

        <div v-else-if="segment.type === 'tool_result'" class="my-2 border rounded-md overflow-hidden bg-slate-50 border-slate-200 w-full" data-testid="tool-result">
          <details class="group tool-details">
            <summary class="px-3 py-2 text-xs font-mono font-medium text-slate-600 cursor-pointer hover:bg-slate-100 flex items-center gap-2 select-none">
              <span class="text-emerald-600">🤖</span> Resultado del Agente
            </summary>
            <div class="p-3 border-t border-slate-200 bg-slate-900 text-slate-50 text-xs font-mono overflow-x-auto tool-content">
              <pre>{{ segment.content }}</pre>
            </div>
          </details>
        </div>
      </template>
    </div>
  </div>
</template>

<style>
.prose p {
  margin-bottom: 0.5em;
}
.prose pre {
  margin: 0.5em 0;
  background-color: #1e293b;
  color: #e2e8f0;
  padding: 0.75rem;
  border-radius: 0.375rem;
  overflow-x: auto;
}
.tool-details > .tool-content {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 0.25s ease, opacity 0.25s ease;
}
.tool-details[open] > .tool-content {
  max-height: 480px;
  opacity: 1;
  overflow: auto;
}
</style>
