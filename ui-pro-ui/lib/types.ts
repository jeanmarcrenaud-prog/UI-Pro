// UI-Pro Types
// ============

export type MessageRole = "user" | "assistant" | "system" | "agent"

export type MessageStatus = "thinking" | "streaming" | "done" | "error"

export interface Message {
  id: string
  role: MessageRole
  content: string
  status?: MessageStatus
  timestamp?: string
}

export interface AgentStep {
  id: string
  title: string
  detail?: string
  status: "pending" | "active" | "done"
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
  currentStep: number
  steps: AgentStep[]
}
