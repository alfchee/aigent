import type { ChatMessage, Conversation } from '@/types/chat'

export function exportConversationAsJson(conv: Conversation, messages: ChatMessage[]) {
  const payload = {
    conversation: conv,
    messages,
    exportedAt: Date.now(),
  }
  return JSON.stringify(payload, null, 2)
}

export function exportConversationAsTxt(conv: Conversation, messages: ChatMessage[]) {
  const header = `# ${conv.title}\n# export: ${new Date().toISOString()}\n\n`
  const lines = messages
    .map((m) => {
      const ts = new Date(m.createdAt).toLocaleString()
      const who = m.role === 'user' ? 'Tú' : m.role === 'assistant' ? 'Agente' : 'Sistema'
      return `[${ts}] ${who}:\n${m.text}\n`
    })
    .join('\n')
  return header + lines
}

export function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
