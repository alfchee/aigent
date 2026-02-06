<script setup lang="ts">
import { ref } from 'vue'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<Message[]>([
  { role: 'assistant', content: '¡Hola! Soy Navibot. ¿En qué puedo ayudarte hoy?' }
])
const newMessage = ref('')
const isLoading = ref(false)

async function sendMessage() {
  if (!newMessage.value.trim() || isLoading.value) return

  const userContent = newMessage.value
  messages.value.push({ role: 'user', content: userContent })
  newMessage.value = ''
  isLoading.value = true

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userContent })
    })
    
    if (!response.ok) throw new Error('Network response was not ok')
    
    const data = await response.json()
    messages.value.push({ role: 'assistant', content: data.response || 'No recibí respuesta del agente.' })
  } catch (error) {
    console.error('Error sending message:', error)
    messages.value.push({ role: 'assistant', content: 'Lo siento, hubo un error al conectar con el servidor.' })
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="h-screen w-screen flex flex-col bg-slate-50 text-slate-900 font-sans overflow-hidden">
    <!-- Header -->
    <header class="p-4 bg-white border-b border-slate-200 flex justify-between items-center shadow-sm z-10">
      <div class="flex items-center gap-3">
        <div class="bg-sky-500 p-2 rounded-lg text-white">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
          </svg>
        </div>
        <h1 class="text-xl font-bold tracking-tight">Navibot <span class="text-sky-500 font-medium font-mono text-sm border border-sky-100 bg-sky-50 px-2 py-0.5 rounded ml-1">v2.0</span></h1>
      </div>
    </header>

    <!-- Chat display -->
    <main class="flex-1 overflow-y-auto p-4 md:p-8 flex flex-col items-center bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-fixed">
      <div class="w-full max-w-3xl space-y-6">
        <div 
          v-for="(msg, index) in messages" 
          :key="index"
          :class="['flex w-full animate-in fade-in slide-in-from-bottom-2 duration-300', msg.role === 'user' ? 'justify-end' : 'justify-start']"
        >
          <div 
            :class="[
              'max-w-[85%] p-4 rounded-2xl shadow-md text-sm leading-relaxed',
              msg.role === 'user' 
                ? 'bg-sky-600 text-white rounded-tr-none' 
                : 'bg-white text-slate-800 border border-slate-100 rounded-tl-none'
            ]"
          >
            <div class="flex gap-2 items-center mb-1 pb-1 border-b border-white/10" :class="msg.role === 'user' ? 'border-sky-400' : 'border-slate-100'">
              <span class="text-[10px] font-bold uppercase tracking-widest opacity-70">{{ msg.role === 'user' ? 'Tú' : 'Navibot' }}</span>
            </div>
            <p class="whitespace-pre-wrap">{{ msg.content }}</p>
          </div>
        </div>
        
        <!-- Loading indicator -->
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
    </main>

    <!-- Input area -->
    <footer class="p-4 bg-white border-t border-slate-200">
      <div class="max-w-3xl mx-auto">
        <form @submit.prevent="sendMessage" class="flex gap-2 relative">
          <textarea
            v-model="newMessage"
            placeholder="Escribe un mensaje..."
            rows="1"
            class="flex-1 p-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 transition-all resize-none text-sm pr-12"
            :disabled="isLoading"
            @keydown.enter.prevent="sendMessage"
          ></textarea>
          <button
            type="submit"
            :disabled="isLoading || !newMessage.trim()"
            class="absolute right-2 bottom-2 p-2 bg-sky-500 text-white rounded-lg hover:bg-sky-600 disabled:opacity-50 disabled:bg-slate-300 transition-colors shadow-sm"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </button>
        </form>
        <p class="text-[10px] text-center text-slate-400 mt-2">© 2026 Navibot Agent · Powered by DeepMind</p>
      </div>
    </footer>
  </div>
</template>

<style>
/* Reset and global styles */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, #app {
  height: 100%;
  width: 100%;
  margin: 0;
  padding: 0;
}

::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}
</style>
