// lib/messageAdapter.ts
// Role: Normalize messages from different sources (WebSocket backend, REST fallback, events)
// into a unified format to eliminate fragmentation and improve testability

import type { Message } from '@/lib/types'

export type MessageType = 'token' | 'step' | 'tool' | 'done' | 'error' | 'unknown'

export interface NormalizedMessage {
  type: MessageType
  content: string
  messageId?: string
  stepId?: string
  status?: 'pending' | 'active' | 'done'
  tokenCount?: number
  duration?: number  // Node execution duration in seconds
  code?: string
  title?: string
}

/**
 * Normalize messages from various sources into consistent format
 * Handles: backend WebSocket format, REST fallback, event emitter format
 */
export function normalizeMessage(raw: any): NormalizedMessage {
  if (!raw) {
    return { type: 'unknown', content: '' }
  }

  // Determine type (backend sends multiple formats)
  const type = determineType(raw)

  // Extract content (various field names)
  const content = extractContent(raw)

  // Extract metadata
  const messageId = raw.message_id || raw.id || raw.messageId
  const stepId = raw.step_id || raw.stepId
  const status = normalizeStatus(raw.status || raw.step_status)
  const tokenCount = raw.token_count || raw.tokenCount
  const duration = raw.duration
  const code = raw.code
  const title = raw.title || raw.step_title

  return {
    type,
    content,
    messageId,
    stepId,
    status,
    tokenCount,
    duration,
    code,
    title,
  }
}

/**
 * Determine message type from various format indicators
 */
function determineType(msg: any): MessageType {
  // Explicit type
  if (msg.type === 'token' || msg.type === 'step' || msg.type === 'done' || msg.type === 'error' || msg.type === 'tool') {
    return msg.type
  }

  // Implicit type detection
  if (msg.delta && msg.status === 'streaming') return 'token'
  if (msg.response && !msg.step_id) return 'token'
  if (msg.content && msg.step_id) return 'step'
  if (msg.done === true || msg.status === 'done') return 'done'
  if (msg.message && msg.type === 'error') return 'error'
  if (msg.type === 'tool') return 'tool'

  return 'unknown'
}

/**
 * Extract content from various field names
 */
function extractContent(msg: any): string {
  return (
    msg.content ||
    msg.delta ||
    msg.response ||
    msg.message ||
    msg.data ||
    msg.token ||
    ''
  ).toString()
}

/**
 * Normalize status values
 */
function normalizeStatus(
  status: string | undefined
): NormalizedMessage['status'] {
  if (status === 'pending' || status === 'active' || status === 'done') {
    return status
  }
  return undefined
}

/**
 * Convert normalized message back to Message type for store
 */
export function toStoreMessage(normalized: NormalizedMessage, assistantId: string): Message {
  return {
    id: normalized.messageId || assistantId,
    role: 'assistant',
    content: normalized.content,
    delta: normalized.content,
    status: normalized.status as any || 'streaming',
    type: normalized.type,
    step_id: normalized.stepId,
  }
}
