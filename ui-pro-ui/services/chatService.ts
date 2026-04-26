// chatService.ts

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

  private activeRequest: {
    id: string
    prompt: string
    model: string
    assistantId: string
  } | null = null

  private streamSeq = 0
  private started = false
  private lastFlush = 0

  private connectPromise: Promise<void> | null = null
  private isFallingBack = false
  private manuallyClosed = false

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
  // STREAM HANDLER
  // =====================
  private handleMessage = (event: MessageEvent) => {
    const msg = this.parse(event.data)
    if (!msg || typeof msg !== 'object') return

    if (msg.type === 'pong') return

    // unify routing
    const requestId = msg.message_id || msg.request_id
    if (this.activeRequest && requestId && requestId !== this.activeRequest.id) return

    // step event
    if (msg.type === 'step') {
      events.emit('agentStep', {
        stepId: msg.step_id,
        status: msg.step_status || 'active',
      })
      return
    }

    // error event
    if (msg.type === 'error') {
      this.stop()
      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: msg.message || msg.error || 'Error',
        status: 'error',
      })
      return
    }

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

      events.emit('status', { status: 'idle' })
    }
  }

  // =====================
  // CONNECTION
  // =====================
  private connect(): Promise<void> {
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
      const wsUrl = API_CONFIG.wsUrl.replace('localhost', host)

      this.ws = new WebSocket(wsUrl)

      const timeout = setTimeout(() => {
        this.ws?.close()
        fail(new Error('WS timeout'))
      }, 8000)

      this.ws.onopen = () => {
        clearTimeout(timeout)

        this.lifecycleState = 'open'

        this.timers.heartbeat = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 15000)

        ok()
      }

      this.ws.onerror = () => {
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
  // PUBLIC API
  // =====================
  async sendMessage(content: string) {
    if (this.lifecycleState === 'connecting' || this.lifecycleState === 'open') {
      if (this.activeRequest) throw new Error('Request in progress')
    }

    const id = crypto.randomUUID()

    this.activeRequest = {
      id,
      prompt: content,
      model:
        useUIStore.getState().selectedModel ||
        useUIStore.getState().availableModels[0] ||
        'qwen3.5:9b',
      assistantId: crypto.randomUUID(),
    }

    this.resetStream()

    try {
      await this.connect()

      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        throw new Error('WS not ready')
      }

      this.ws.send(
        JSON.stringify({
          message_id: id,
          message: content,
          model: this.activeRequest.model,
        })
      )
    } catch (e) {
      await this.fallback()
    }
  }

  stop() {
    this.manuallyClosed = true
    this.clearTimers()
    this.activeRequest = null
    this.resetStream()

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
    if (this.manuallyClosed || this.isFallingBack) return

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