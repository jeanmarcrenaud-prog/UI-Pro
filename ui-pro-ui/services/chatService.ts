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

  // Fix: Lifecycle state to prevent race conditions
  private lifecycleState: 'idle' | 'connecting' | 'open' | 'closing' | 'fallback' = 'idle'

  // Fix: Track assistant message for single-message updates
  private assistantMessageId: string | null = null

  // Fix: Throttle for smooth 60fps streaming
  private lastFlush = 0

  private state = {
    messageId: null as string | null,
    fullContent: '',
    started: false,
    reconnects: 0,
    lastModel: null as string | null,
    lastPrompt: '',
  }

  // Fix: Use enum instead of boolean for clearer intent
  private closeReason: 'user' | 'system' | 'error' | null = null
  private promptMap = new Map<string, string>()  // Fix: Bind prompts to messageId
  private connectPromise: Promise<void> | null = null  // Fix: Prevent concurrent connections
  private isFallingBack = false  // Fix: Prevent duplicate fallback calls

  private timers = {
    flush: null as ReturnType<typeof setTimeout> | null,
    heartbeat: null as ReturnType<typeof setInterval> | null,
  }

  // =====================
  // CLEAN HELPERS
  // =====================
  private resetState() {
    this.state.fullContent = ''
    this.state.started = false
    this.assistantMessageId = null
  }

  private clearTimers() {
    // Fix: Clear and reset refs to null
    if (this.timers.flush) {
      clearTimeout(this.timers.flush)
      this.timers.flush = null
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
      // Fix: Simplified - just parse the raw data
      const msg = this.parseMessageData(event.data)
      
      if (!msg || typeof msg !== 'object') return

      // Heartbeat / Pong
      if (msg.type === 'pong') return

      // Fix: Only filter if both message_id exist
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
        // Fix: Delta model - accumulate fullContent but emit delta
        this.state.fullContent += text

        // Create message with delta for UI accumulation
        const deltaMsg = {
          id: this.assistantMessageId || crypto.randomUUID(),
          role: 'assistant' as const,
          content: this.state.fullContent,
          delta: text,  // Incremental chunk for UI
          status: 'streaming' as const,
        }
        this.assistantMessageId = deltaMsg.id

        // Throttle to ~60fps but always emit
        const now = Date.now()
        if (now - this.lastFlush >= 16) {
          this.lastFlush = now
          this.emit(deltaMsg)
        } else if (!this.timers.flush) {
          this.timers.flush = setTimeout(() => {
            this.emit(deltaMsg)
            this.timers.flush = null
          }, 16)
        }
      }

      // Handle Done signal
      if (msg.done || msg.type === 'done') {
        // Fix: Always emit final content on done (no condition check)
        if (this.assistantMessageId) {
          this.emit({
            id: this.assistantMessageId,
            role: 'assistant',
            content: this.state.fullContent,
            status: 'done',
          })
        }
        this.state.messageId = null
        this.state.started = false
        this.state.fullContent = ''
        this.clearTimers()
        this.lifecycleState = 'idle'
        this.assistantMessageId = null
        events.emit('status', { status: 'idle' })
      }
    } catch (e) {
      console.error('[ChatService] Error handling WS message:', e)
    }
  }

  private flushBuffer(final = false) {
    if (!this.state.fullContent) {
      if (final) {
        this.assistantMessageId = null
        this.state.fullContent = ''
      }
      return
    }

    // Fix: Single message ID for streaming updates
    if (!this.assistantMessageId) {
      this.assistantMessageId = crypto.randomUUID()
      this.emit({
        id: this.assistantMessageId,
        role: 'assistant',
        content: this.state.fullContent,
        status: final ? 'done' : 'streaming',
      })
    } else {
      this.emit({
        id: this.assistantMessageId,
        role: 'assistant',
        content: this.state.fullContent,
        status: final ? 'done' : 'streaming',
      })
    }

    if (final) {
      this.assistantMessageId = null
      this.state.fullContent = ''
    }
  }

  // =====================
  // CONNECTION
  // =====================
  private connect(): Promise<void> {
    // Fix: Prevent concurrent connections
    if (this.connectPromise) {
      return this.connectPromise
    }

    this.lifecycleState = 'connecting'  // Fix: Set lifecycle state

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
        this.lifecycleState = 'open'  // Fix: Set lifecycle state

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
        // Fix: Handle close regardless of settlement state
        // If settled=true: connection was successful, still need cleanup
        // If settled=false: connection failed before establishing

        // Cleanup first
        this.ws = null
        this.lifecycleState = 'closing'

        clearTimeout(timeoutId)
        this.clearTimers()

        // Fix: Don't reconnect if manually closed
        if (this.manuallyClosed) {
          console.log('[ChatService] Socket manually closed')
          this.lifecycleState = 'idle'
          if (!settled) {
            safeReject(new Error(`[ChatService] Socket manually closed (code: ${ev.code})`))
          }
          return
        }

        // Clean close (1000 = normal, 1001 = going away)
        if (ev.code === 1000 || ev.code === 1001) {
          this.lifecycleState = 'idle'
          if (!settled) {
            safeReject(new Error(`[ChatService] Socket closed cleanly (code: ${ev.code})`))
          }
          return
        }

        // Reconnect with backoff - only if connection was not established
        if (!settled) {
          // Connection failed before establishing - try fallback
          if (this.state.reconnects < 5) {
            this.state.reconnects++
            console.log(`[ChatService] Reconnecting (${this.state.reconnects}/5)...`)
            setTimeout(() => {
              this.fallback()
            }, Math.min(500 * this.state.reconnects, 3000))
          } else {
            console.warn('[ChatService] Max reconnects reached. Falling back to HTTP.')
            this.fallback()
          }
          safeReject(new Error(`[ChatService] WebSocket closed before connection (code: ${ev.code})`))
        } else {
          // Established connection dropped during streaming: switch to HTTP
          console.log('[ChatService] Connection dropped during conversation')
          this.fallback()
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
    // Fix: Use lifecycleState guard for state machine
    if (this.lifecycleState === 'connecting' || this.lifecycleState === 'open') {
      if (this.state.messageId) {
        throw new Error('Message already in progress')
      }
    }

    this.resetState()
    this.state.messageId = messageId || crypto.randomUUID()
    this.state.lastPrompt = content
    this.promptMap.set(this.state.messageId, content)  // Fix: Bind prompt to messageId

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
    this.lifecycleState = 'closing'  // Fix: Set lifecycle state
    // Fix: Safe ws close
    const ws = this.ws
    this.ws = null
    ws?.close()
    this.lifecycleState = 'idle'
    events.emit('status', { status: 'idle' })
  }

  private async fallback() {
    // Fix: Check manuallyClosed - prevent fallback after intentional close
    if (this.manuallyClosed) {
      return
    }
    // Fix: Single guard - set flag first to prevent race
    if (this.isFallingBack) {
      return
    }
    this.isFallingBack = true
    this.lifecycleState = 'fallback'

    const host = window.location.hostname || 'localhost'
    const msgId = this.state.messageId
    const fallbackMessage = this.promptMap.get(msgId || '') || this.state.lastPrompt || ''

    try {
      // Fix: Use API_CONFIG with messageId-bound prompt
      const apiUrl = API_CONFIG.apiUrl.replace('localhost', host) + '/api/chat'
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          // Fix: Use prompt from map (bound to messageId)
          message: fallbackMessage,
          model: useUIStore.getState().selectedModel,
        }),
      })

      if (!res.ok) throw new Error('HTTP fallback failed')
      const data = await res.json()
      const fallbackContent = data?.result ?? data?.message ?? 'Response received but content unavailable.'

      // Fix: Single message update
      if (!this.assistantMessageId) {
        this.assistantMessageId = crypto.randomUUID()
      }
      this.emit({
        id: this.assistantMessageId,
        role: 'assistant',
        content: typeof fallbackContent === 'string' ? fallbackContent : 'Response received but content unavailable.',
        status: 'done',
      })
    } catch {
      // Fix: Single error message
      if (!this.assistantMessageId) {
        this.assistantMessageId = crypto.randomUUID()
      }
      this.emit({
        id: this.assistantMessageId,
        role: 'assistant',
        content: 'Connection failed. Backend unreachable.',
        status: 'error',
      })
    } finally {
      this.isFallingBack = false
      // Fix: Don't reset manuallyClosed - only stop()/cancel() should set it
      this.state.messageId = null
      this.lifecycleState = 'idle'
      this.assistantMessageId = null
      events.emit('status', { status: 'idle' })
    }
  }
}

export const chatService = new ChatService()
