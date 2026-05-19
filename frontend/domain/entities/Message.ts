// domain/entities/Message.ts
// Role: Core domain types for messages and agent steps

export type MessageRole = 'user' | 'assistant' | 'system' | 'agent';

export type MessageStatus = 'thinking' | 'streaming' | 'done' | 'error';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  delta?: string;
  status?: MessageStatus;
  timestamp?: string;
  done?: boolean;
  message_id?: string;
  type?: string;
  step_id?: string;
}

export type AgentStepStatus = 'pending' | 'active' | 'done' | 'error';

export interface AgentStep {
  id: string;
  title: string;
  detail?: string;
  status: AgentStepStatus;
}

export interface AssistantMessage extends Message {
  role: 'assistant';
}

export interface AgentMessage extends Message {
  role: 'agent';
  steps: AgentStep[];
}

export interface ChatHistoryItem {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
  tags?: string[];
  archived?: boolean;
  isPinned?: boolean;
}

export interface UseChatReturn {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  isActive: boolean;
  currentStep: AgentStep | undefined;
  steps: AgentStep[];
  sendMessage: (content: string) => void;
  clear: () => void;
  cancel: () => void;
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
}

export interface AgentState {
  isActive: boolean;
  steps: AgentStep[];
  currentStepId?: string;
  currentStep?: number;
}

export interface ChatRequest {
  message: string;
}

export interface ChatResponse {
  result: string;
  status: 'success' | 'error';
}
