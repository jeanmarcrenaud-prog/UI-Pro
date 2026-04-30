// hooks/index.ts
// Role: Barrel exports for all React hooks - exposes useChat and its return type for external import

// Hooks index
export { useChat } from './useChat'

// Streaming hooks
export { useStream } from './useStream'
export { useWebSocket, mapStreamEvent } from './useWebSocket'