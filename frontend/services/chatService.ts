// services/chatService.ts
/**
 * Chat Service - Orchestrator for WebSocket + SSE/REST fallback
 * 
 * Architecture:
 * - ChatService: Main orchestrator (lightweight)
 * - WebSocketManager: Connection lifecycle + heartbeat
 * - MessageHandler: Parse and emit messages
 * - FallbackHandler: SSE/REST fallbacks with AbortController
 * 
 * Refactored for:
 * - Single Responsibility
 * - Better testability
 * - Cleaner state management
 */

import type { Message } from '@/lib/types'
import { events } from '@/lib/events'
import { API_CONFIG } from '@/lib/config'
import { WebSocketManager } from './WebSocketManager'
import { MessageHandler } from './MessageHandler'
import { FallbackHandler } from './FallbackHandler'
import { DEFAULT_MODEL, DEFAULT_PROVIDER, MAX_HANDLERS, REQUEST_TIMEOUT } from './constants'
import type { ActiveRequest, PendingModel } from './types'

class ChatService {
  // Dependencies
  private wsManager = new WebSocketManager()
  private fallback = new FallbackHandler()
  private messageHandler: MessageHandler

  // State
  private handlers = new Set<(message: Message) => void>()
  private activeRequest: ActiveRequest | null = null
  private manuallyClosed = false
  private pendingModel: PendingModel | null = null

  constructor() {
    // Initialize message handler with bound callbacks
    this.messageHandler = new MessageHandler(
      this.handleToken.bind(this),
      this.handleStep.bind(this),
      this.handleError.bind(this),
      this.handleComplete.bind(this)
    )
  }

  // =====================
  // PUBLIC API
  // =====================

  onMessage(handler: (message: Message) => void): () => void {
    if (this.handlers.size >= MAX_HANDLERS) {
      console.warn('[chatService] Max handlers reached, clearing')
      this.handlers.clear()
    }
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  async sendMessage(
    content: string,
    resumeMessageId?: string,
    resumeChunkIndex = 0,
    model?: string,
    provider?: string
  ): Promise<void> {
    // Capture model before creating request
    const effectiveModel = model || this.pendingModel?.model || DEFAULT_MODEL
    const effectiveProvider = provider || this.pendingModel?.provider || DEFAULT_PROVIDER
    this.pendingModel = null

    // Wait for existing request
    if (this.activeRequest) {
      console.warn('[chatService] Request in progress, waiting...')
      const start = Date.now()
      while (this.activeRequest && Date.now() - start < REQUEST_TIMEOUT) {
        await new Promise(r => setTimeout(r, 100))
      }
      if (this.activeRequest) {
        this.stop()
      }
    }

    // Create request
    this.activeRequest = {
      id: resumeMessageId || crypto.randomUUID(),
      prompt: content,
      model: effectiveModel,
      provider: effectiveProvider,
      assistantId: crypto.randomUUID(),
      lastChunkIndex: resumeChunkIndex,
    }
    this.manuallyClosed = false

    // Try WebSocket first
    try {
      await this.wsManager.connect(
        (data) => this.messageHandler.process(data, this.activeRequest),
        () => this.handleClose()
      )
      this.sendPayload()
    } catch (error) {
      console.warn('[chatService] WS failed, trying fallback...', error)
      await this.tryFallback()
    }
  }

  setModel(model: string, provider: string = DEFAULT_PROVIDER): void {
    this.pendingModel = { model, provider }
  }

  cancel(): void {
    this.fallback.cancel()
    this.wsManager.send({ type: 'cancel' })
    this.stop()
  }

  stop(): void {
    this.manuallyClosed = true
    this.activeRequest = null
    this.wsManager.close()
    this.fallback.cancel()
    events.emit('status', { status: 'idle' })
  }

  destroy(): void {
    this.stop()
    this.handlers.clear()
    this.pendingModel = null
  }

  // =====================
  // INTERNAL - Payload
  // =====================

  private sendPayload(): void {
    if (!this.activeRequest) return
    this.wsManager.send({
      message_id: this.activeRequest.id,
      message: this.activeRequest.prompt,
      model: this.activeRequest.model,
      provider: this.activeRequest.provider,
      last_chunk_index: this.activeRequest.lastChunkIndex,
    })
  }

  // =====================
  // INTERNAL - Handlers (bound methods)
  // =====================

  private handleToken(id: string, content: string, done: boolean): void {
    this.emit({ id, role: 'assistant', content, delta: content, status: done ? 'done' : 'streaming' })
  }

  private handleStep(stepId: string, status: string): void {
    events.emit('agentStep', { stepId, status: status as 'pending' | 'active' | 'done' })
  }

  private handleError(message: string): void {
    this.emit({ id: crypto.randomUUID(), role: 'assistant', content: message, status: 'error' })
    this.clearRequest()
  }

  private handleComplete(id: string): void {
    this.emit({ id, role: 'assistant', content: '', status: 'done' })
    this.clearRequest()
  }

  // =====================
  // INTERNAL - Connection Management
  // =====================

  private handleClose(): void {
    if (!this.manuallyClosed && this.activeRequest) {
      this.tryReconnect()
    }
  }

  private async tryReconnect(): Promise<void> {
    while (this.activeRequest && this.wsManager.canReconnect()) {
      this.wsManager.incrementReconnect()
      const delay = this.wsManager.calculateReconnectDelay()
      
      await new Promise(r => setTimeout(r, delay))
      
      if (this.manuallyClosed || !this.activeRequest) break

      try {
        await this.wsManager.connect(
          (data) => this.messageHandler.process(data, this.activeRequest),
          () => this.handleClose()
        )
        this.sendPayload()
        return // Success
      } catch {
        // Continue loop
      }
    }

    await this.tryFallback()
  }

  private async tryFallback(): Promise<void> {
    if (!this.activeRequest) return

    const host = window.location.hostname || 'localhost'
    const baseUrl = API_CONFIG.apiUrl.replace('localhost', host)
    const streamUrl = `${baseUrl}/api/stream`
    console.log('[chatService] tryFallback:', { host, baseUrl, streamUrl })
    
    const { prompt, model, provider, assistantId } = this.activeRequest

    // Try SSE
    const sseSuccess = await this.fallback.sendSSE(
      streamUrl,
      { message: prompt, model, provider },
      (content, done) => this.emit({ id: assistantId, role: 'assistant', content, delta: content, status: done ? 'done' : 'streaming' })
    )

    if (sseSuccess) {
      this.clearRequest()
      return
    }

    // Fall back to REST
    try {
      const text = await this.fallback.sendREST(`${baseUrl}/api/chat`, { message: prompt, model, provider })
      this.emit({ id: assistantId, role: 'assistant', content: text, status: 'done' })
    } catch {
      this.handleError('Backend unreachable')
    }

    this.clearRequest()
  }

  private clearRequest(): void {
    this.activeRequest = null
    this.manuallyClosed = true
    this.wsManager.close()
    events.emit('status', { status: 'idle' })
  }

  private emit(message: Message): void {
    this.handlers.forEach(h => h(message))
  }
}

export const chatService = new ChatService()