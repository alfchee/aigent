export type Role = 'user' | 'assistant' | 'system';

export interface Message {
  id: string;
  role: Role;
  content: string;
  timestamp: number;
  isStreaming?: boolean;
}

// Backend Event Types
export type EventType = 
  | 'start' 
  | 'iteration_start' 
  | 'thinking' 
  | 'tool_call' 
  | 'observation' 
  | 'response' 
  | 'completion' 
  | 'final' 
  | 'error';

export interface BackendEvent<T = any> {
  type: EventType;
  data: T;
  timestamp?: string;
}

// Data Payloads
export interface ThinkingPayload {
  message: string;
  iteration?: number;
}

export interface ToolCallPayload {
  tool_name: string;
  arguments: Record<string, any>;
}

export interface ObservationPayload {
  result: any;
  tool_name?: string; // Sometimes useful to link back
}

export interface ResponsePayload {
  text: string;
}

// Internal Console/Log Types
export interface LogEntry {
  id: string;
  type: 'info' | 'thinking' | 'tool' | 'error' | 'success';
  title: string;
  details?: any;
  timestamp: number;
  expanded?: boolean;
}

export type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'completed' | 'error';
