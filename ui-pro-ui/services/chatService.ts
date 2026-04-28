// chatService.ts - Chat Service with Auto-Reconnect + Resume Support
//
// Role: WebSocket client with intelligent resume, fallback, and reconnect
// Used by: Chat component, MessageInput
// - Real-time streaming
// - Auto-reconnect with exponential backoff
// - Resume from last chunk on reconnect
// - REST fallback when WebSocket fails

import type { Message } from '@/lib/types'
import { useUIStore } from '@/lib/stores/uiStore'
import { events } from '@/lib/events'
import { API_CONFIG } from '@/lib/config'

class ChatService {
  private ws: WebSocket | null = null

  private handlers = new Set<(m: Message) => void>()

  // =====================
  // STATE MACHINE
  // =====================
  private lifecycleState: 'idle' | 'connecting' | 'open' | 'closing' | 'fallback' = 'idle'

  // Current active request with resume data
  private activeRequest: {
    id: string
    prompt: string
    model: string
    assistantId: string
    lastChunkIndex: number
  } | null = null

  private streamSeq = 0
  private started = false
  private lastFlush = 0

  private connectPromise: Promise<void> | null = null
  private isFallingBack = false
  private manuallyClosed = false

  // =====================
  // RECONNECT MANAGEMENT
  // =====================
  private reconnectAttempts = 0
  private readonly MAX_RECONNECT_ATTEMPTS = 5
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  private timers = {
    flush: null as ReturnType<typeof setTimeout> | null,
    heartbeat: null as ReturnType<typeof setInterval> | null,
  }

  // =====================
  // HELPERS
  // =====================
  private emit(msg: Message) {
    this.handlers.forEach(h => h(msg))
  }

  onMessage(handler: (m: Message) => void) {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  private resetStream() {
    this.started = false
    this.streamSeq = 0
  }

  private clearTimers() {
    if (this.timers.flush) clearTimeout(this.timers.flush)
    if (this.timers.heartbeat) clearInterval(this.timers.heartbeat)
    this.timers.flush = null
    this.timers.heartbeat = null
  }

  private parse(data: any) {
    if (typeof data !== 'string') return data
    try {
      return JSON.parse(data)
    } catch {
      return null
    }
  }

  // =====================
  // MESSAGE HANDLER
  // =====================
  private handleMessage = (event: MessageEvent) => {
    const msg = this.parse(event.data)
    if (!msg || typeof msg !== 'object') return

    if (msg.type === 'pong') return

    // Unify routing
    const requestId = msg.message_id || msg.request_id
    if (this.activeRequest && requestId && requestId !== this.activeRequest.id) return

    // Resume acknowledgment from backend
    if (msg.type === 'resume_ack') {
      console.log(`[chatService] Resume acknowledge: resuming_from=${msg.resuming_from}, current_chunk=${msg.current_chunk}`)
      if (this.activeRequest && msg.resuming_from) {
        this.activeRequest.lastChunkIndex = Math.max(
          this.activeRequest.lastChunkIndex,
          Number(msg.resuming_from) || 0
        )
      }
      return
    }

    // Step event
    if (msg.type === 'step') {
      console.log('[chatService] Step:', msg.step_id, 'status:', msg.status, 'rawStatus:', msg.step_status || msg.status)

      let stepStatus: 'pending' | 'active' | 'done' = 'pending'
      const rawStatus = msg.step_status || msg.status || ''
      if (rawStatus === 'done' || rawStatus === 'completed') {
        stepStatus = 'done'
      } else if (rawStatus === 'starting' || rawStatus === 'generating' || rawStatus === 'active') {
        stepStatus = 'active'
      }

      events.emit('agentStep', {
        stepId: msg.step_id,
        status: stepStatus,
      })
      return
    }

    // Error event
    if (msg.type === 'error') {
      this.stop()
      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: msg.message || msg.error || 'An error occurred',
        status: 'error',
      })
      return
    }

    // Token streaming
    const text =
      msg.content ||
      msg.text ||
      msg.token ||
      msg.data ||
      msg.response ||
      ''

    if (!this.started && text) {
      this.started = true
      events.emit('status', { status: 'streaming' })
    }

    if (text && this.activeRequest) {
      this.streamSeq++

      const delta: Message = {
        id: this.activeRequest.assistantId,
        role: 'assistant',
        content: '',
        delta: text,
        status: 'streaming',
      }

      const now = Date.now()

      if (now - this.lastFlush >= 16) {
        this.lastFlush = now
        this.emit(delta)
      } else if (!this.timers.flush) {
        this.timers.flush = setTimeout(() => {
          this.emit(delta)
          this.timers.flush = null
        }, 16)
      }
    }

    // Stream finished
    if (msg.done || msg.type === 'done') {
      if (this.activeRequest) {
        this.emit({
          id: this.activeRequest.assistantId,
          role: 'assistant',
          content: '',
          status: 'done',
        })
      }

      this.resetStream()
      this.activeRequest = null
      this.clearTimers()
      this.lifecycleState = 'idle'
      this.reconnectAttempts = 0 // Reset on success

      events.emit('status', { status: 'idle' })
    }
  }

  // =====================
  // CONNECTION WITH RECONNECT
  // =====================
  private async connect(): Promise<void> {
    if (this.connectPromise) return this.connectPromise

    this.lifecycleState = 'connecting'

    this.connectPromise = new Promise((resolve, reject) => {
      let settled = false

      const ok = () => {
        if (!settled) {
          settled = true
          resolve()
        }
      }

      const fail = (e: Error) => {
        if (!settled) {
          settled = true
          reject(e)
        }
      }

      this.manuallyClosed = false

      if (this.ws?.readyState === WebSocket.OPEN) {
        ok()
        return
      }

      this.ws?.close()

      const host = window.location.hostname || 'localhost'
      const wsUrl = API_CONFIG.wsUrl.replace('localhost', host) + '/ws'
      console.log('[chatService] Connecting to:', wsUrl)

      this.ws = new WebSocket(wsUrl)

      // Connection timeout
      const timeout = setTimeout(() => {
        console.log('[chatService] Connection timeout')
        this.ws?.close()
        fail(new Error('WS timeout'))
      }, 10000)

      this.ws.onopen = () => {
        console.log('[chatService] WebSocket opened')
        clearTimeout(timeout)

        this.lifecycleState = 'open'
        this.reconnectAttempts = 0 // Reset on successful connect

        this.timers.heartbeat = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 15000)

        ok()
      }

      this.ws.onerror = () => {
        console.log('[chatService] WebSocket error')
        clearTimeout(timeout)
        fail(new Error('WS error'))
      }

      this.ws.onmessage = this.handleMessage

      this.ws.onclose = () => {
        this.ws = null
        this.lifecycleState = 'closing'
        this.clearTimers()

        if (this.manuallyClosed) {
          this.lifecycleState = 'idle'
          return
        }

        this.lifecycleState = 'idle'
        fail(new Error('WS closed'))
      }
    })

    return this.connectPromise.finally(() => {
      this.connectPromise = null
    })
  }

  // =====================
  // SEND MESSAGE WITH RESUME
  // =====================
  async sendMessage(content: string, resumeMessageId?: string, resumeChunkIndex = 0) {
    if (this.activeRequest) {
      throw new Error('A request is already in progress')
    }

    const messageId = resumeMessageId || crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    this.activeRequest = {
      id: messageId,
      prompt: content,
      model:
        useUIStore.getState().selectedModel ||
        useUIStore.getState().availableModels[0] ||
        'qwen3.5:9b',
      assistantId,
      lastChunkIndex: resumeChunkIndex,
    }

    this.resetStream()
    this.reconnectAttempts = 0

    try {
      await this.connect()

      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        throw new Error('WS not ready')
      }

      console.log('[chatService] Sending message:', {
        message_id: messageId,
        model: this.activeRequest.model,
        last_chunk_index: resumeChunkIndex
      })

      this.ws.send(
        JSON.stringify({
          message_id: messageId,
          message: content,
          model: this.activeRequest.model,
          last_chunk_index: resumeChunkIndex,
        })
      )
      console.log('[chatService] Message sent')
    } catch (e) {
      console.warn('[chatService] WebSocket failed, attempting reconnect...', e)
      await this.attemptReconnect()
    }
  }

  // =====================
  // AUTO RECONNECT
  // =====================
  private async attemptReconnect() {
    if (this.manuallyClosed || !this.activeRequest || this.reconnectAttempts >= this.MAX_RECONNECT_ATTEMPTS) {
      console.log('[chatService] Max reconnect attempts reached or manually closed, falling back...')
      await this.fallback()
      return
    }

    this.reconnectAttempts++
    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 8000)

    console.log(`[chatService] Reconnect attempt ${this.reconnectAttempts}/${this.MAX_RECONNECT_ATTEMPTS} in ${delay}ms`)

    this.reconnectTimeout = setTimeout(async () => {
      if (this.activeRequest) {
        try {
          await this.sendMessage(
            this.activeRequest.prompt,
            this.activeRequest.id,
            this.activeRequest.lastChunkIndex
          )
        } catch (e) {
          console.warn('[chatService] Reconnect failed, retrying...', e)
          await this.attemptReconnect()
        }
      }
    }, delay)
  }

  // =====================
  // STOP & CANCEL
  // =====================
  stop() {
    this.manuallyClosed = true
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout)
    this.clearTimers()
    this.activeRequest = null
    this.resetStream()
    this.reconnectAttempts = 0

    const ws = this.ws
    this.ws = null
    ws?.close()

    this.lifecycleState = 'idle'
    events.emit('status', { status: 'idle' })
  }

  cancel() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'cancel' }))
    }
    this.stop()
  }

  // =====================
  // FALLBACK
  // =====================
  private async fallback() {
    if (this.manuallyClosed || this.isFallingBack || !this.activeRequest) return

    this.isFallingBack = true
    this.lifecycleState = 'fallback'

    const req = this.activeRequest
    const host = window.location.hostname || 'localhost'

    try {
      const res = await fetch(
        API_CONFIG.apiUrl.replace('localhost', host) + '/api/chat',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: req?.prompt || '',
            model: req?.model,
          }),
        }
      )

      const data = await res.json()
      const text =
        data?.result ?? data?.message ?? 'No response available'

      const id = req?.assistantId || crypto.randomUUID()

      this.emit({
        id,
        role: 'assistant',
        content: text,
        status: 'done',
      })
    } catch {
      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Backend unreachable',
        status: 'error',
      })
    } finally {
      this.isFallingBack = false
      this.activeRequest = null
      this.lifecycleState = 'idle'
      events.emit('status', { status: 'idle' })
    }
  }
}

export const chatService = new ChatService()