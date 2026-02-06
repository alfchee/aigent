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
  
  const logs = ref<LogEntry[]>([]); // Keeping global logs for now, might be useful for debug
  const status = ref<StreamStatus>('idle');
  const currentThought = ref<string>('');
  const abortController = ref<AbortController | null>(null);
  
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

  function addMessageLog(msgId: string, type: LogEntry['type'], title: string, details?: any) {
    const msg = messages.value.find(m => m.id === msgId);
    if (msg) {
      if (!msg.steps) msg.steps = [];
      msg.steps.push({
        id: crypto.randomUUID(),
        type,
        title,
        details,
        timestamp: Date.now(),
        expanded: false // Default collapsed in message view
      });
    }
    // Also add to global logs for now
    addLog(type, title, details);
  }

  function stopGeneration() {
    if (abortController.value) {
      abortController.value.abort();
      abortController.value = null;
    }
    status.value = 'completed'; // Or 'cancelled' if we had that state
    currentThought.value = '';
    
    // Find the last streaming message and mark it as done
    const lastMsg = messages.value.find(m => m.isStreaming);
    if (lastMsg) {
      lastMsg.isStreaming = false;
    }
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
      isStreaming: true,
      steps: []
    });
    
    currentThought.value = '';
    
    // Init AbortController
    abortController.value = new AbortController();

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
        signal: abortController.value.signal,
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
          if (abortController.value?.signal.aborted) {
             // Ignore if aborted manually
             return;
          }
          status.value = 'error';
          addMessageLog(assistantMsgId, 'error', 'Connection Error', err);
          throw err; // rethrow to stop retries by default, or handle logic
        }
      });
    } catch (err: any) {
       if (abortController.value?.signal.aborted) {
         console.log('Stream aborted by user');
         return;
       }
      console.error('Stream error:', err);
      status.value = 'error';
      finalizeStream(assistantMsgId);
    }
  }

  function handleBackendEvent(event: BackendEvent, msgId: string) {
    // Update transient thought
    const msg = messages.value.find(m => m.id === msgId);
    
    switch (event.type) {
      case 'start':
        addMessageLog(msgId, 'info', 'Process Started');
        break;
        
      case 'iteration_start':
        const iterData = event.data as ThinkingPayload;
        addMessageLog(msgId, 'info', `Iteration ${iterData.iteration || '?'}`, iterData);
        break;
        
      case 'thinking':
        const thinkData = event.data as ThinkingPayload;
        currentThought.value = thinkData.message;
        if (msg) msg.currentThought = thinkData.message;
        addMessageLog(msgId, 'thinking', 'Thinking', thinkData.message);
        break;
        
      case 'tool_call':
        const toolData = event.data as ToolCallPayload;
        addMessageLog(msgId, 'tool', `Calling Tool: ${toolData.tool_name}`, toolData.arguments);
        currentThought.value = `Executing ${toolData.tool_name}...`;
        if (msg) msg.currentThought = `Executing ${toolData.tool_name}...`;
        break;
        
      case 'observation':
        const obsData = event.data as ObservationPayload;
        addMessageLog(msgId, 'success', `Tool Result`, obsData.result);
        break;
        
      case 'response':
        const respData = event.data as ResponsePayload;
        // Append text to the current message
        if (msg) {
          msg.content += respData.text;
          // Clear transient thought when responding
          msg.currentThought = undefined;
          currentThought.value = 'Responding...';
        }
        break;
        
      case 'completion':
      case 'final':
        // Task done
        break;
        
      case 'error':
        addMessageLog(msgId, 'error', 'Backend Error', event.data);
        break;
    }
  }

  function finalizeStream(msgId: string) {
    status.value = 'completed';
    currentThought.value = '';
    abortController.value = null;
    const msg = messages.value.find(m => m.id === msgId);
    if (msg) {
      msg.isStreaming = false;
      msg.currentThought = undefined;
    }
  }

  return {
    messages,
    logs,
    status,
    currentThought,
    isStreaming,
    hasLogs,
    sendMessage,
    stopGeneration
  };
});
