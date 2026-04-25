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
  }

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
    if (this.timers.flush) clearTimeout(this.timers.flush)
    if (this.timers.stream) clearTimeout(this.timers.stream)
    if (this.timers.heartbeat) clearInterval(this.timers.heartbeat)
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

    // Try standard JSON parse first
    try {
      return JSON.parse(rawMsg)
    } catch {
      // Fallback: Handle potential double-encoding or concatenated JSON
      // Attempt to find JSON objects in the string
      try {
        // Regex to find the first valid JSON object { ... }
        const jsonMatch = rawMsg.match(/\{[^{}]+\}/)
        if (jsonMatch) {
          return JSON.parse(jsonMatch[0])
        }
      } catch (e) {
        console.warn('[ChatService] Failed to parse concatenated JSON', e)
      }
    }
    return rawMsg
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

      // Handle Step events
      if (msg.type === 'step' || msg.status) {
        events.emit('agentStep', {
          stepId: msg.step_id || msg.status,
          status: msg.status || 'active',
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
      if (!this.state.started && (msg.content || msg.text || msg.token)) {
        this.state.started = true
        events.emit('status', { status: 'streaming' })
      }

      // Normalize text content (handle multiple potential field names)
      const text = msg.content || msg.text || msg.token || msg.response || msg.thinking || ''

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
        this.flushBuffer(true) // Flush remaining buffer as final
        
        this.emit({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: this.state.content,
          status: 'done',
        })

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
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        resolve()
        return
      }

      if (this.ws) {
        this.ws.close()
      }

      const model = useUIStore.getState().selectedModel
      
      // Use dynamic host (window.location.hostname) for the frontend to work in any environment
      // Use config for port - derive from wsUrl or use default
      const host = window.location.hostname || 'localhost'
      const wsUrl = `ws://${host}:8000/ws`
      console.log('[ChatService] Connecting to', wsUrl)
      this.ws = new WebSocket(wsUrl)

      // Timeout after 8s
      const timeoutId = setTimeout(() => {
        this.ws?.close()
        reject(new Error('[ChatService] WebSocket connection timeout'))
      }, 8000)

      this.ws.onopen = () => {
        clearTimeout(timeoutId)
        console.log('[ChatService] WebSocket connected')
        this.state.lastModel = model
        this.state.reconnects = 0

        this.timers.heartbeat = setInterval(() => {
          this.ws?.send(JSON.stringify({ type: 'ping' }))
        }, 15000)

        resolve()
      }

      this.ws.onmessage = this.handleMessage

      this.ws.onerror = (err) => {
        clearTimeout(timeoutId)
        console.error('[ChatService] WebSocket error:', err)
        // Reject instead of resolve - don't let caller think connection succeeded
        reject(new Error('[ChatService] WebSocket error'))
      }

      this.ws.onclose = (ev) => {
        clearTimeout(timeoutId)
        this.clearTimers()
        // Only reset reconnects on clean close (code 1000) or 1001
        if (ev.code >= 1000 && ev.code !== 1006) {
          this.state.reconnects = 6 // Trigger immediate fallback
        }
        if (this.state.reconnects < 6) {
          this.state.reconnects++
          console.log(`[ChatService] Reconnecting (${this.state.reconnects}/6)...`)
          setTimeout(() => this.connect(), Math.min(500 * this.state.reconnects, 3000))
        } else {
          console.warn('[ChatService] Max reconnects reached. Falling back to HTTP.')
          this.fallback()
          reject(new Error('[ChatService] Max reconnects reached'))
        }
      }
    })
  }

  // =====================
  // PUBLIC API
  // =====================
  async sendMessage(content: string, messageId?: string) {
    this.resetState()
    this.state.messageId = messageId || crypto.randomUUID()

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

      this.ws?.send(JSON.stringify(payload))
    } catch (err) {
      console.error('[ChatService] Failed to send message:', err)
      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Connection failed. Please try again.',
        status: 'error',
      })
    }
  }

  cancel() {
    this.stop()
    this.ws?.send(
      JSON.stringify({
        type: 'cancel',
        message_id: this.state.messageId,
      })
    )
  }

  stop() {
    this.clearTimers()
    this.state.started = false
    this.state.messageId = null
    this.ws?.close()
    this.ws = null
    events.emit('status', { status: 'idle' })
  }

  private async fallback() {
    const host = window.location.hostname || 'localhost'
    try {
      // Use dynamic host for HTTP fallback too
      const apiUrl = `http://${host}:8000/api/chat`
      const res = await fetch(
        apiUrl,
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: this.state.content, // Or the original content
            model: useUIStore.getState().selectedModel,
          }),
        }
      )

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
    }
    events.emit('status', { status: 'idle' })
  }
}

export const chatService = new ChatService()
