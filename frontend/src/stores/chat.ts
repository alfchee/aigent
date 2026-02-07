import { defineStore } from 'pinia'

import { fetchJson } from '../lib/api'

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

type ChatResponse = {
  response: string
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [
      { role: 'assistant', content: '¡Hola! Soy Navibot. ¿En qué puedo ayudarte hoy?' }
    ] as ChatMessage[],
    isLoading: false as boolean,
    error: null as string | null
  }),
  actions: {
    async sendMessage(message: string, sessionId: string) {
      const trimmed = message.trim()
      if (!trimmed || this.isLoading) return
      this.messages.push({ role: 'user', content: trimmed })
      this.isLoading = true
      this.error = null
      try {
        const data = await fetchJson<ChatResponse>('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: trimmed, session_id: sessionId })
        })
        this.messages.push({ role: 'assistant', content: data.response || 'No recibí respuesta del agente.' })
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
        this.messages.push({ role: 'assistant', content: 'Lo siento, hubo un error al conectar con el servidor.' })
      } finally {
        this.isLoading = false
      }
    }
  }
})

