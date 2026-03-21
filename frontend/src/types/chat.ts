export type MessageRole = 'user' | 'assistant' | 'system'

export type MessageStatus = 'sending' | 'sent' | 'delivered' | 'read' | 'error'

export type Conversation = {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  tags: string[]
  agentId?: string
  folder?: string
  archived?: boolean
}

export type ChatMessage = {
  id: string
  conversationId: string
  role: MessageRole
  text: string
  createdAt: number
  status: MessageStatus
  meta?: Record<string, unknown>
}

export type ExecutionEventType = 'status' | 'tool_call' | 'error'

export type ExecutionEvent = {
  id: string
  type: ExecutionEventType
  label: string
  details?: string
  createdAt: number
}

export type OutboundWsEnvelope =
  | {
      type: 'user_message'
      sessionId: string
      conversationId: string
      messageId: string
      text: string
      createdAt: number
      agentId?: string
      e2ee?: boolean
    }
  | {
      type: 'ping'
      sessionId: string
      ts: number
    }

export type InboundWsEnvelope =
  | {
      type: 'ack'
      content?: string
      ts?: number
    }
  | {
      type: 'assistant_message'
      conversationId: string
      messageId: string
      text: string
      createdAt: number
    }
  | {
      type: 'status'
      state?: string
      action?: string
      details?: string
      state_snapshot?: AgentStateSnapshot
      stage?: string
      refine_status?: RefineStatusInfo
    }
  | {
      type: 'tool_call'
      tool_name?: string
      details?: string
    }
  | {
      type: 'error'
      content?: string
      conversationId?: string
      ts?: number
    }
  | {
      type: 'pong'
      ts: number
    }
  | {
      type: string
      [k: string]: unknown
    }

export type RefineStatusInfo = {
  stage: 'idle' | 'refining' | 'approved' | 'revised' | 'incomplete' | 'error'
  criteria?: string[]
  result?: string
}

export type WorkerStatusInfo = {
  role_id: string
  name: string
  current_task?: string
  completed_at?: string
  status: 'idle' | 'working' | 'error'
}

export type AgentStateSnapshot = {
  session_id: string
  user_id: string
  last_activity: string
  active_worker?: string
  workers: Record<string, WorkerStatusInfo>
  last_tool_used?: string
  last_tool_result?: string
  total_turns: number
  total_errors: number
  pending_tasks: string[]
  completed_tasks: Array<{
    task_id: string
    description: string
    status: string
    started_at: string
    completed_at?: string
  }>
  refine_status?: RefineStatusInfo
}
