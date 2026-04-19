// UI-Pro Types
// ============

export type MessageRole = "user" | "assistant" | "system" | "agent"

export type MessageStatus = "thinking" | "streaming" | "done" | "error"

export type AgentStepStatus = "pending" | "active" | "done" | "error"

export interface Message {
  id: string
  role: MessageRole
  content: string
  status?: MessageStatus
  timestamp?: string
  done?: boolean
  message_id?: string  // For WebSocket deduplication
}

export interface AgentStep {
  id: string
  title: string
  detail?: string
  status: AgentStepStatus
}

// UseChat hook return type
export interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  error: string | null
  isActive: boolean
  currentStep: AgentStep | undefined
  steps: AgentStep[]
  sendMessage: (content: string) => void
  clear: () => void
  cancel: () => void
}

export interface AgentMessage extends Message {
  role: "agent"
  steps: AgentStep[]
}

// API Types
export interface ChatRequest {
  message: string
}

export interface ChatResponse {
  result: string
  status: "success" | "error"
}

// Store Types
export interface ChatState {
  messages: Message[]
  isLoading: boolean
  error: string | null
}

export interface AgentState {
  isActive: boolean
  steps: AgentStep[]
  currentStepId?: string // Current step ID (for lookup)
  currentStep?: number   // Current step index (for progress)
}

// History Types
export interface ChatHistoryItem {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}
