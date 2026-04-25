// chatService.ts
// Role: Singleton WebSocket service - manages backend connection, message streaming,
// reconnection logic, and HTTP fallback for real-time AI chat communication

// Chat Service - WebSocket communication with backend
import type { Message } from '@/lib/types'
import { useUIStore } from '@/lib/stores/uiStore'
import { events } from '@/lib/events'
import { API_CONFIG } from '@/lib/config'

class ChatService {
  private ws: WebSocket | null = null

  private handlers = new Set<(m: Message) => void>()

  private state = {
    messageId: null as string | null,
    content: '',
    buffer: '',
    started: false,
    reconnects: 0,
    lastModel: null as string | null,
    lastPrompt: '',  // Fix: Store last prompt for fallback
  }

  private manuallyClosed = false  // Fix: Prevent auto-reconnect after intentional close
  private connectPromise: Promise<void> | null = null  // Fix: Prevent concurrent connections
  private isFallingBack = false  // Fix: Prevent duplicate fallback calls

  private timers = {
    flush: null as ReturnType<typeof setTimeout> | null,
    stream: null as ReturnType<typeof setTimeout> | null,
    heartbeat: null as ReturnType<typeof setInterval> | null,
  }

  // =====================
  // CLEAN HELPERS
  // =====================
  private resetState() {
    this.state.content = ''
    this.state.buffer = ''
    this.state.started = false
  }

  private clearTimers() {
    // Fix: Clear and reset refs to null
    if (this.timers.flush) {
      clearTimeout(this.timers.flush)
      this.timers.flush = null
    }
    if (this.timers.stream) {
      clearTimeout(this.timers.stream)
      this.timers.stream = null
    }
    if (this.timers.heartbeat) {
      clearInterval(this.timers.heartbeat)
      this.timers.heartbeat = null
    }
  }

  private emit(msg: Message) {
    this.handlers.forEach((h) => h(msg))
  }

  onMessage(handler: (m: Message) => void) {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  // Parse message data - handles SSE JSON format
  private parseMessageData(rawMsg: any): any {
    // If rawMsg is already an object, return it
    if (typeof rawMsg !== 'string') return rawMsg

    // Fix: Robust JSON parsing
    try {
      return JSON.parse(rawMsg)
    } catch {
      console.warn('[ChatService] Failed to parse message:', rawMsg.substring(0, 50))
      return null
    }
  }

  // =====================
  // STREAM HANDLER
  // =====================
  private handleMessage = (event: MessageEvent) => {
    try {
      const rawMsg = typeof event.data === 'string' ? event.data : event.data
      const msg = this.parseMessageData(rawMsg)
      
      if (!msg || typeof msg !== 'object') return

      // Heartbeat / Pong
      if (msg.type === 'pong') return

      // FIX: message_id mismatch check (removed duplicate)
      if (this.state.messageId && msg.message_id && msg.message_id !== this.state.messageId) {
        return
      }

      // Handle Step events - only trigger on explicit step type
      if (msg.type === 'step') {
        events.emit('agentStep', {
          stepId: msg.step_id,
          status: msg.step_status || 'active',
        })
        return
      }

      // Handle Error events
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

      // Handle Stream Start (detect first token)
      if (!this.state.started && (msg.content || msg.text || msg.token || msg.data)) {
        this.state.started = true
        events.emit('status', { status: 'streaming' })
      }

      // Normalize text content (handle multiple potential field names)
      const text = msg.content || msg.text || msg.token || msg.response || msg.thinking || msg.data || ''

      if (text) {
        this.state.content += text
        this.state.buffer += text

        // Throttle buffer flush to avoid excessive re-renders
        if (!this.timers.flush) {
          this.timers.flush = setTimeout(() => {
            this.flushBuffer()
            this.timers.flush = null
          }, 30)
        }
      }

      // Handle Done signal
      if (msg.done || msg.type === 'done') {
        this.flushBuffer(true) // Flush remaining buffer and emit as 'done'
        this.state.messageId = null  // Fix: Clear after done
        this.stop()
        events.emit('status', { status: 'idle' })
      }
    } catch (e) {
      console.error('[ChatService] Error handling WS message:', e)
    }
  }

  private flushBuffer(final = false) {
    if (!this.state.buffer) return

    this.emit({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: this.state.buffer,
      status: final ? 'done' : 'streaming',
    })

    this.state.buffer = ''
  }

  // =====================
  // CONNECTION
  // =====================
  private connect(): Promise<void> {
    // Fix: Prevent concurrent connections
    if (this.connectPromise) {
      return this.connectPromise
    }

    // Fix: Create promise first, then start connection logic
    this.connectPromise = new Promise((resolve, reject) => {
      // Fix: Prevent multiple resolve/reject calls
      let settled = false
      const safeResolve = () => {
        if (!settled) {
          settled = true
          resolve()
        }
      }
      const safeReject = (error: Error) => {
        if (!settled) {
          settled = true
          reject(error)
        }
      }
      
      this.manuallyClosed = false
      
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        safeResolve()
        return
      }

      if (this.ws) {
        this.ws.close()
      }

      const host = window.location.hostname || 'localhost'
      // Fix: Use API_CONFIG
      const wsUrl = API_CONFIG.wsUrl.replace('localhost', host)
      console.log('[ChatService] Connecting to:', wsUrl)
      this.ws = new WebSocket(wsUrl)

      // Timeout after 8s
      const timeoutId = setTimeout(() => {
        this.ws?.close()
        safeReject(new Error('[ChatService] WebSocket connection timeout'))
      }, 8000)

      this.ws.onopen = () => {
        clearTimeout(timeoutId)
        console.log('[ChatService] WebSocket connected')
        this.state.lastModel = useUIStore.getState().selectedModel
        this.state.reconnects = 0

        // Fix: Secure heartbeat
        this.timers.heartbeat = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 15000)

        safeResolve()
      }

      this.ws.onmessage = this.handleMessage

      this.ws.onerror = (err) => {
        clearTimeout(timeoutId)
        console.error('[ChatService] WebSocket error:', err)
        safeReject(new Error('[ChatService] WebSocket error'))
      }

      this.ws.onclose = (ev) => {
        // Fix: Prevent race condition - don't process if already settled
        // This avoids double fallback when timeout + onclose both fire
        if (settled) {
          return
        }

        // Fix: Clear WebSocket reference to prevent stale state
        this.ws = null

        clearTimeout(timeoutId)
        this.clearTimers()
        
        // Fix: Don't reconnect if manually closed
        if (this.manuallyClosed) {
          console.log('[ChatService] Socket manually closed')
          return
        }
        
        // Clean close
        if (ev.code === 1000 || ev.code === 1001) {
          return
        }
        
        // Reconnect with backoff
        if (this.state.reconnects < 5) {
          this.state.reconnects++
          console.log(`[ChatService] Reconnecting (${this.state.reconnects}/5)...`)
          setTimeout(() => {
            this.connectPromise = null  // Fix: Clear before reconnect
            this.fallback()  // Fix: Use fallback instead of WS reconnect
          }, Math.min(500 * this.state.reconnects, 3000))
        } else {
          console.warn('[ChatService] Max reconnects reached. Falling back to HTTP.')
          this.fallback()
          safeReject(new Error('[ChatService] Max reconnects reached'))
        }
      }
    })

    // Fix: Cleanup after resolve/reject
    return this.connectPromise.finally(() => {
      this.connectPromise = null
    })
  }

  // =====================
  // PUBLIC API
  // =====================
  async sendMessage(content: string, messageId?: string) {
    // Fix: Prevent concurrent messages without throwing
    if (this.state.messageId) {
      console.warn('[ChatService] Message already in progress')
      return
    }

    this.resetState()
    this.state.messageId = messageId || crypto.randomUUID()
    this.state.lastPrompt = content  // Fix: Store for fallback

    try {
      await this.connect()

      const selectedModel = useUIStore.getState().selectedModel
      const availableModels = useUIStore.getState().availableModels
      
      const model = selectedModel || availableModels[0] || 'qwen3.5:9b'
      
      const payload = {
        message_id: this.state.messageId,
        message: content,
        model: model,
      }

      // Fix: Verify WebSocket is OPEN before sending
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        throw new Error('WebSocket not ready')
      }

      this.ws.send(JSON.stringify(payload))
    } catch (err) {
      console.error('[ChatService] Failed to send:', err)
      // Fix: Use fallback instead of just emitting error
      await this.fallback()
    }
  }

  cancel() {
    // Fix: Send cancel before stopping (ws becomes null after stop)
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'cancel',
        message_id: this.state.messageId,
      }))
    }
    this.stop()
  }

  stop() {
    this.manuallyClosed = true  // Fix: Prevent auto-reconnect
    this.clearTimers()
    this.state.started = false
    this.state.messageId = null
    // Fix: Safe ws close
    const ws = this.ws
    this.ws = null
    ws?.close()
    events.emit('status', { status: 'idle' })
  }

  private async fallback() {
    // Fix: Prevent multiple fallback calls
    if (this.isFallingBack) return
    this.isFallingBack = true

    const host = window.location.hostname || 'localhost'
    try {
      // Fix: Use API_CONFIG
      const apiUrl = API_CONFIG.apiUrl.replace('localhost', host) + '/api/chat'
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          // Fix: Use lastPrompt instead of empty content
          message: this.state.lastPrompt || this.state.content,
          model: useUIStore.getState().selectedModel,
        }),
      })

      if (!res.ok) throw new Error('HTTP fallback failed')
      const data = await res.json()
      const fallbackContent = data?.result ?? data?.message ?? 'Response received but content unavailable.'

      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: typeof fallbackContent === 'string' ? fallbackContent : 'Response received but content unavailable.',
        status: 'done',
      })
    } catch {
      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Connection failed. Backend unreachable.',
        status: 'error',
      })
    } finally {
      this.isFallingBack = false
      this.state.messageId = null
      events.emit('status', { status: 'idle' })
    }
  }
}

export const chatService = new ChatService()
