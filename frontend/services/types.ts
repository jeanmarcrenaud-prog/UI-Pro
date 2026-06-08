// services/types.ts
// Shared types for chat service

export type LifecycleState = 'idle' | 'connecting' | 'open' | 'closing' | 'fallback'

export interface ActiveRequest {
  id: string
  prompt: string
  model: string
  provider: string
  assistantId: string
  lastChunkIndex: number
}

export interface PendingModel {
  model: string
  provider: string
}

export interface FallbackParams {
  message: string
  model: string
  provider: string
}

export type TokenCallback = (id: string, content: string, done: boolean) => void
export type StepCallback = (stepId: string, status: string, content?: string) => void
export type ErrorCallback = (message: string) => void
export type CompleteCallback = (id: string) => void
export type ApprovalCallback = (streamId: string, codePreview: string, messageId: string) => void
export type MessageHandlerCallback = (content: string, done: boolean) => void