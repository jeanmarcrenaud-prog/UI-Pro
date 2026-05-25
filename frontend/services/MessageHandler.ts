// services/MessageHandler.ts
// Parse and emit messages from WebSocket/SSE

import { WS_EVENTS } from './constants'
import type { ActiveRequest, TokenCallback, StepCallback, ErrorCallback, CompleteCallback } from './types'
import { debugLogger } from '@/lib/debug/logger'

export class MessageHandler {
  constructor(
    private onToken: TokenCallback,
    private onStep: StepCallback,
    private onError: ErrorCallback,
    private onComplete: CompleteCallback
  ) {}

  process(data: any, activeRequest: ActiveRequest | null): void {
    // Validate schema
    if (!data || typeof data !== 'object') {
      console.warn('[MessageHandler] Invalid data:', data)
      return
    }

    const type = data.type

    // Handle resume acknowledgment
    if (type === WS_EVENTS.RESUME_ACK && activeRequest) {
      activeRequest.lastChunkIndex = Math.max(
        activeRequest.lastChunkIndex,
        Number(data.resuming_from) || 0
      )
      debugLogger.logInfo('Resume acknowledged', 'resume')
      return
    }

    // Handle agent step (including generation stats from LLM)
    if (type === WS_EVENTS.STEP) {
      const stepId = data.step_id
      const status = data.step_status || data.status || 'active'
      const title = data.title || stepId
      const content = data.content || ''
      if (stepId && typeof stepId === 'string') {
        // Log full step content to Debug Panel (stats message, step detail, etc.)
        debugLogger.logStep(title, content || `Status: ${status}`, { duration: 0 })
        this.onStep(stepId, status)
      }
      return
    }

    // Handle error
    if (type === WS_EVENTS.ERROR) {
      const msg = data.message || data.error || 'Unknown error'
      debugLogger.logError(msg, data)
      if (msg) this.onError(msg)
      return
    }

    // Handle cancelled (from stop button)
    if (type === 'cancelled') {
      debugLogger.logInfo('Request cancelled by user', 'cancel')
      this.onComplete(activeRequest?.assistantId || '')
      return
    }

    // Handle token/content
    const content = data.response || data.content || data.data || data.token || ''
    const done = data.done || type === WS_EVENTS.DONE || data.status === 'completed'

    if (content && activeRequest) {
      const tokens = data.token_count || 0
      debugLogger.logToken(content, tokens)
      this.onToken(activeRequest.assistantId, content, done)
    }

    // Handle completion
    if (done && activeRequest) {
      debugLogger.logInfo('Request completed', 'complete')
      this.onComplete(activeRequest.assistantId)
    }
  }
}