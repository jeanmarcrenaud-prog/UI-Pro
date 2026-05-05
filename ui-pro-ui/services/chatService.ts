// services/chatService.ts
/**
 * Chat Service - WebSocket client with auto-reconnect and resume support
 * Used for real-time streaming with fallback to REST
 */

import type { Message } from '@/lib/types'
import { events } from '@/lib/events'
import { API_CONFIG } from '@/lib/config'

type LifecycleState = 'idle' | 'connecting' | 'open' | 'closing' | 'fallback'

interface ActiveRequest {
  id: string
  prompt: string
  model: string
  provider: string  // ollama, lmstudio, lemonade, llamacpp
  assistantId: string
  lastChunkIndex: number
}

class ChatService {
  private ws: WebSocket | null = null
  private handlers = new Set<(message: Message) => void>()

  private lifecycleState: LifecycleState = 'idle'
  private activeRequest: ActiveRequest | null = null

  private reconnectAttempts = 0
  private readonly MAX_RECONNECT_ATTEMPTS = 5
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  private timers = {
    flush: null as ReturnType<typeof setTimeout> | null,
    heartbeat: null as ReturnType<typeof setInterval> | null,
  }

  private manuallyClosed = false
  private isFallingBack = false

  // =====================
  // PUBLIC API
  // =====================

  onMessage(handler: (message: Message) => void) {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  async sendMessage(content: string, resumeMessageId?: string, resumeChunkIndex = 0, model?: string, provider?: string) {
    if (this.activeRequest) {
      console.warn('[chatService] A request is already in progress')
      return
    }

    const messageId = resumeMessageId || crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    this.activeRequest = {
      id: messageId,
      prompt: content,
      model: model || 'qwen3.5:9b',
      provider: provider || 'ollama',
      assistantId,
      lastChunkIndex: resumeChunkIndex,
    }

    this.reconnectAttempts = 0
    this.manuallyClosed = false

    try {
      await this.connect()
      this.sendOverWebSocket()
    } catch (error) {
      console.warn('[chatService] WebSocket connection failed, trying reconnect...', error)
      await this.attemptReconnect()
    }
  }

  // Set model AFTER initialization (so caller controls it)
  setModel(model: string, provider: string = 'ollama') {
    if (this.activeRequest) {
      this.activeRequest.model = model
      this.activeRequest.provider = provider
    }
  }

  cancel() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'cancel' }))
    }
    this.stop()
  }

  stop() {
    this.manuallyClosed = true
    this.clearAllTimers()
    this.activeRequest = null
    this.reconnectAttempts = 0

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    this.lifecycleState = 'idle'
    events.emit('status', { status: 'idle' })
  }

  // =====================
  // INTERNAL
  // =====================

  private async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) return

    return new Promise((resolve, reject) => {
      this.lifecycleState = 'connecting'

      const host = window.location.hostname || 'localhost'
      const wsUrl = `${API_CONFIG.wsUrl.replace('localhost', host)}/ws`

      this.ws = new WebSocket(wsUrl)

      const timeoutId = setTimeout(() => {
        this.ws?.close()
        reject(new Error('WebSocket connection timeout'))
      }, 8000)

      this.ws.onopen = () => {
        clearTimeout(timeoutId)
        this.lifecycleState = 'open'
        this.reconnectAttempts = 0
        this.startHeartbeat()
        resolve()
      }

      this.ws.onerror = () => {
        clearTimeout(timeoutId)
        reject(new Error('WebSocket connection error'))
      }

      this.ws.onmessage = this.handleMessage
      this.ws.onclose = this.handleClose
    })
  }

  private sendOverWebSocket() {
    if (!this.ws || !this.activeRequest) return

    this.ws.send(
      JSON.stringify({
        message_id: this.activeRequest.id,
        message: this.activeRequest.prompt,
        model: this.activeRequest.model,
        provider: this.activeRequest.provider,
        last_chunk_index: this.activeRequest.lastChunkIndex,
      })
    )
  }

  private handleMessage = (event: MessageEvent) => {
    let msg: any
    try {
      msg = typeof event.data === 'string' ? JSON.parse(event.data) : event.data
    } catch {
      return
    }

    if (msg.type === 'pong') return
    if (msg.type === 'resume_ack') {
      if (this.activeRequest && msg.resuming_from !== undefined) {
        this.activeRequest.lastChunkIndex = Math.max(
          this.activeRequest.lastChunkIndex,
          Number(msg.resuming_from) || 0
        )
      }
      return
    }

    // Step events
    if (msg.type === 'step') {
      events.emit('agentStep', {
        stepId: msg.step_id,
        status: msg.step_status || msg.status || 'active',
      })
      return
    }

    // Error
    if (msg.type === 'error') {
      this.emitError(msg.message || msg.error || 'Unknown error')
      return
    }

    const content = msg.response || msg.content || msg.data || msg.token || ''

    // Token streaming
    if (content && this.activeRequest) {
      this.emit({
        id: this.activeRequest.assistantId,
        role: 'assistant',
        content: '', // full content is built in the store
        delta: content,
        status: 'streaming',
      })
    }

    // Stream completed
    if (msg.done || msg.type === 'done' || msg.status === 'completed') {
      this.emitCompletion()
    }
  }

  private handleClose = () => {
    this.ws = null
    this.clearAllTimers()

    if (this.manuallyClosed) {
      this.lifecycleState = 'idle'
      return
    }

    this.attemptReconnect()
  }

  private async attemptReconnect() {
    if (this.manuallyClosed || !this.activeRequest || this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
      await this.fallback()
      return
    }

    this.reconnectAttempts++
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 10000)

    this.reconnectTimeout = setTimeout(async () => {
      try {
        await this.sendMessage(
          this.activeRequest!.prompt,
          this.activeRequest!.id,
          this.activeRequest!.lastChunkIndex
        )
      } catch {
        await this.attemptReconnect()
      }
    }, delay)
  }

  private async fallback() {
    if (!this.activeRequest || this.isFallingBack) return
    this.isFallingBack = true

    try {
      const host = window.location.hostname || 'localhost'
      const response = await fetch(
        `${API_CONFIG.apiUrl.replace('localhost', host)}/api/chat`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: this.activeRequest.prompt,
            model: this.activeRequest.model,
            provider: this.activeRequest.provider,
          }),
        }
      )

      const data = await response.json()
      const text = data?.result || data?.response || data?.message || ''

      this.emit({
        id: this.activeRequest.assistantId,
        role: 'assistant',
        content: text,
        status: 'done',
      })
    } catch {
      this.emitError('Backend unreachable - fallback failed')
    } finally {
      this.isFallingBack = false
      this.activeRequest = null
      this.lifecycleState = 'idle'
    }
  }

  private emit(message: Message) {
    this.handlers.forEach((handler) => handler(message))
  }

  private emitError(message: string) {
    this.emit({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: message,
      status: 'error',
    })
    this.stop()
  }

  private emitCompletion() {
    if (this.activeRequest) {
      this.emit({
        id: this.activeRequest.assistantId,
        role: 'assistant',
        content: '',
        status: 'done',
      })
    }
    this.stop()
  }

  private startHeartbeat() {
    this.clearAllTimers()
    this.timers.heartbeat = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 15000)
  }

  private clearAllTimers() {
    if (this.timers.flush) clearTimeout(this.timers.flush)
    if (this.timers.heartbeat) clearInterval(this.timers.heartbeat)
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout)

    this.timers.flush = null
    this.timers.heartbeat = null
    this.reconnectTimeout = null
  }
}

export const chatService = new ChatService()