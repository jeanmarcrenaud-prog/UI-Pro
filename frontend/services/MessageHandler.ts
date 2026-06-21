// services/MessageHandler.ts
// Parse and emit messages from WebSocket/SSE

import { WS_EVENTS } from './constants'
import type {
  ActiveRequest,
  TokenCallback,
  StepCallback,
  ErrorCallback,
  CompleteCallback,
  ApprovalCallback,
} from './types'
import { events } from '@/lib/events'
import { debugLogger } from '@/lib/debug/logger'

export class MessageHandler {
  constructor(
    private onToken: TokenCallback,
    private onStep: StepCallback,
    private onError: ErrorCallback,
    private onComplete: CompleteCallback,
    private onApproval: ApprovalCallback,
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
        debugLogger.logStep(title, content || `Status: ${status}`, { duration: data.duration || 0 })
        this.onStep(stepId, status, content, data.duration, data.token_count)
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

    // Handle human-in-the-loop execution approval
    if (type === 'awaiting_approval') {
      const streamId = data.stream_id || ''
      const codePreview = data.code_preview || data.content || ''
      const msgId = data.message_id || ''
      debugLogger.logInfo(`Awaiting approval for stream: ${streamId}`, 'approval')
      this.onApproval(streamId, codePreview, msgId)
      return
    }

    // Handle execution output (terminal streaming)
    if (type === WS_EVENTS.EXEC_OUTPUT) {
      const line = data.content || data.data || ''
      const channel = data.channel || 'stdout'
      if (line) {
        events.emit('execOutput', { line, channel })
      }
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