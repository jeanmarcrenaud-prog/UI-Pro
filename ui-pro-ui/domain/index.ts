// domain/index.ts
// Barrel exports for the domain layer - clean architecture entry point

// Entities
export { 
  type MessageRole, 
  type MessageStatus, 
  type AgentStepStatus,
  type Message,
  type AgentStep,
  type AssistantMessage,
  type AgentMessage,
  type ChatHistoryItem,
  type UseChatReturn,
  type ChatState,
  type AgentState,
  type ChatRequest,
  type ChatResponse,
} from './entities/Message'

// Events
export { STREAM_EVENTS, type StreamEventType } from './events/StreamEvents'
export { EventEmitter } from './events/EventEmitter'
export { type EventHandler, type EventMap, type AnyEventHandler } from './events/EventTypes'

// Config
export { 
  API_CONFIG, 
  LLM_CONFIG, 
  type API_CONFIG_TYPE, 
  type LLM_CONFIG_TYPE,
} from './config/Config'
