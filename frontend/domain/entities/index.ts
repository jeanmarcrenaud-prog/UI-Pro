// domain/entities/index.ts
export { type MessageRole, type MessageStatus, type AgentStepStatus } from './Message'
export type {
  Message,
  AgentStep,
  AssistantMessage,
  AgentMessage,
  ChatHistoryItem,
} from './Message'
// Re-exported from lib/types for consistency
export type { ChatState } from '@/lib/types'
