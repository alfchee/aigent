import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import type { 
  Message, 
  LogEntry, 
  StreamStatus, 
  BackendEvent, 
  ThinkingPayload, 
  ToolCallPayload, 
  ObservationPayload, 
  ResponsePayload 
} from '../types/chat';

export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hello! I am NaviBot. I am ready to help you with your tasks.',
      timestamp: Date.now()
    }
  ]);
  
  const logs = ref<LogEntry[]>([]);
  const status = ref<StreamStatus>('idle');
  const currentThought = ref<string>('');
  
  // Getters
  const isStreaming = computed(() => status.value === 'connecting' || status.value === 'streaming');
  const hasLogs = computed(() => logs.value.length > 0);

  // Actions
  function addLog(type: LogEntry['type'], title: string, details?: any) {
    logs.value.push({
      id: crypto.randomUUID(),
      type,
      title,
      details,
      timestamp: Date.now(),
      expanded: true
    });
  }

  async function sendMessage(content: string) {
    if (isStreaming.value || !content.trim()) return;

    // 1. Add User Message
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now()
    });

    // 2. Prepare for Assistant Response
    status.value = 'connecting';
    const assistantMsgId = crypto.randomUUID();
    messages.value.push({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true
    });
    
    // Clear previous transient state if needed, but keep logs? 
    // Maybe better to clear logs for a new turn or keep them? 
    // "Observability Console" usually keeps a history. We'll append.
    currentThought.value = '';

    try {
      await fetchEventSource('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: content,
          use_react_loop: true
        }),
        async onopen(response) {
          if (response.ok) {
            status.value = 'streaming';
            return; // everything's good
          } else {
            status.value = 'error';
            throw new Error(`Failed to connect: ${response.statusText}`);
          }
        },
        onmessage(msg) {
          if (msg.event === 'FatalError') {
            throw new Error(msg.data);
          }
          if (!msg.data) return;

          try {
            const parsedData = JSON.parse(msg.data);
            // Construct the internal event object using the SSE event name as the type
            const event: BackendEvent = {
              type: msg.event as any, // Cast to any or EventType if strictly typed
              data: parsedData,
              timestamp: parsedData.timestamp
            };
            handleBackendEvent(event, assistantMsgId);
          } catch (e) {
            console.error('Failed to parse SSE data:', e);
          }
        },
        onclose() {
          finalizeStream(assistantMsgId);
        },
        onerror(err) {
          status.value = 'error';
          addLog('error', 'Connection Error', err);
          throw err; // rethrow to stop retries by default, or handle logic
        }
      });
    } catch (err) {
      console.error('Stream error:', err);
      status.value = 'error';
      finalizeStream(assistantMsgId);
    }
  }

  function handleBackendEvent(event: BackendEvent, msgId: string) {
    switch (event.type) {
      case 'start':
        addLog('info', 'Process Started');
        break;
        
      case 'iteration_start':
        const iterData = event.data as ThinkingPayload;
        addLog('info', `Iteration ${iterData.iteration || '?'}`, iterData);
        break;
        
      case 'thinking':
        const thinkData = event.data as ThinkingPayload;
        currentThought.value = thinkData.message;
        // Optionally add to log if verbose, or just update UI indicator
        break;
        
      case 'tool_call':
        const toolData = event.data as ToolCallPayload;
        addLog('tool', `Calling Tool: ${toolData.tool_name}`, toolData.arguments);
        currentThought.value = `Executing ${toolData.tool_name}...`;
        break;
        
      case 'observation':
        const obsData = event.data as ObservationPayload;
        addLog('success', `Tool Result`, obsData.result);
        break;
        
      case 'response':
        const respData = event.data as ResponsePayload;
        // Append text to the current message
        const msg = messages.value.find(m => m.id === msgId);
        if (msg) {
          msg.content += respData.text;
        }
        break;
        
      case 'completion':
      case 'final':
        // Task done
        break;
        
      case 'error':
        addLog('error', 'Backend Error', event.data);
        break;
    }
  }

  function finalizeStream(msgId: string) {
    status.value = 'completed';
    currentThought.value = '';
    const msg = messages.value.find(m => m.id === msgId);
    if (msg) {
      msg.isStreaming = false;
    }
  }

  return {
    messages,
    logs,
    status,
    currentThought,
    isStreaming,
    hasLogs,
    sendMessage
  };
});
