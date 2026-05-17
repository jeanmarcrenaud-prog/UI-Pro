// services/MessageHandler.ts
// Parse and emit messages from WebSocket/SSE

import { WS_EVENTS } from './constants'
import type { ActiveRequest, TokenCallback, StepCallback, ErrorCallback, CompleteCallback } from './types'

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
      return
    }

    // Handle agent step
    if (type === WS_EVENTS.STEP) {
      const stepId = data.step_id
      const status = data.step_status || data.status || 'active'
      if (stepId && typeof stepId === 'string') {
        this.onStep(stepId, status)
      }
      return
    }

    // Handle error
    if (type === WS_EVENTS.ERROR) {
      const msg = data.message || data.error || 'Unknown error'
      if (msg) this.onError(msg)
      return
    }

    // Handle token/content
    const content = data.response || data.content || data.data || data.token || ''
    const done = data.done || type === WS_EVENTS.DONE || data.status === 'completed'

    if (content && activeRequest) {
      this.onToken(activeRequest.assistantId, content, done)
    }

    // Handle completion
    if (done && activeRequest) {
      this.onComplete(activeRequest.assistantId)
    }
  }
}