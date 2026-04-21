// Chat Service - WebSocket communication with backend
import type { Message } from '@/lib/types'
import { useUIStore } from '@/lib/stores/uiStore'
import { events } from '@/lib/events'

class ChatService {
  private ws: WebSocket | null = null

  private handlers = new Set<(m: Message) => void>()

  private state = {
    messageId: null as string | null,
    content: '',
    buffer: '',
    lastChunk: 0,
    started: false,
    reconnects: 0,
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
    this.state.lastChunk = 0
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

  // Parse message data - handles double-encoded JSON from backend
  private parseMessageData(rawMsg: any): any {
    // If msg.data exists and is a string, parse it
    if (rawMsg.data && typeof rawMsg.data === 'string') {
      try {
        const dataStr = rawMsg.data
        
        // Try single parse first
        try {
          const inner = JSON.parse(dataStr)
          return { ...rawMsg, ...inner }
        } catch {
          // Multiple concatenated JSON objects - extract responses
          const responses: string[] = []
          const doneFlags: boolean[] = []
          
          // Split by }{ and parse each object
          const objects = dataStr.split(/(?=\{"model")/)
          
          for (const objStr of objects) {
            if (!objStr.trim()) continue
            try {
              const fixed = objStr.startsWith('{') ? objStr : '{' + objStr
              const obj = JSON.parse(fixed)
              if (obj.response) responses.push(obj.response)
              if (obj.thinking) responses.push(obj.thinking)
              doneFlags.push(obj.done || false)
            } catch {
              // Skip malformed objects
            }
          }
          
          if (responses.length > 0) {
            return { 
              ...rawMsg, 
              response: responses.join(''), 
              done: doneFlags[doneFlags.length - 1] || false 
            }
          }
          
          return rawMsg
        }
      } catch {
        return rawMsg
      }
    }
    return rawMsg
  }

  // =====================
  // STREAM HANDLER
  // =====================
  private handleMessage = (event: MessageEvent) => {
    try {
      const rawMsg = JSON.parse(event.data)
      const msg = this.parseMessageData(rawMsg)
      console.log('[ChatService] Parsed message:', msg)

      if (msg.type === 'pong') return

      if (msg.message_id && msg.message_id !== this.state.messageId) {
        console.log('[ChatService] message_id mismatch:', msg.message_id, 'vs', this.state.messageId)
        return
      }

      // STEP
      if (msg.type === 'step') {
        events.emit('agentStep', {
          stepId: msg.step_id,
          status: msg.status,
        })
        return
      }

      // ERROR
      if (msg.type === 'error') {
        this.stop()
        this.emit({
          id: crypto.randomUUID(),
          role: 'assistant',
          content: msg.message,
          status: 'error',
        })
        return
      }

      // STREAM START
      if (!this.state.started && (msg.content || msg.thinking)) {
        this.state.started = true
        events.emit('status', { status: 'streaming' })
      }

      const text = msg.response || msg.thinking || msg.content || ''

      if (text) {
        this.state.content += text
        this.state.buffer += text
        console.log('[ChatService] Token received:', text.slice(0, 50))

        if (!this.timers.flush) {
          this.timers.flush = setTimeout(() => {
            this.flushBuffer()
            this.timers.flush = null
          }, 30)
        }
      } else {
        console.log('[ChatService] No text in message, fields available:', Object.keys(msg))
      }

      // DONE
      if (msg.done) {
        this.flushBuffer(true)

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
      console.warn('[ChatService] parse error', e)
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
    return new Promise((resolve) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        resolve()
        return
      }

      // Close existing socket if not open
      if (this.ws) {
        this.ws.close()
      }

      this.ws = new WebSocket(
        `ws://${window.location.hostname}:8000/ws`
      )

      this.ws.onopen = () => {
        console.log('[ChatService] WebSocket connected')
        this.state.reconnects = 0

        this.timers.heartbeat = setInterval(() => {
          this.ws?.send(JSON.stringify({ type: 'ping' }))
        }, 15000)

        resolve()
      }

      this.ws.onmessage = this.handleMessage

      this.ws.onerror = (err) => {
        console.error('[ChatService] WebSocket error:', err)
      }

      this.ws.onclose = () => {
        console.log('[ChatService] WebSocket closed')
        this.clearTimers()

        if (this.state.reconnects < 3) {
          this.state.reconnects++
          console.log(`[ChatService] Reconnecting (${this.state.reconnects}/3)...`)
          setTimeout(() => this.connect(), 500 * this.state.reconnects)
        } else {
          console.log('[ChatService] Max reconnects reached')
          this.stop()
          this.fallback()
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
      
      // DEBUG: Log everything
      console.log('[ChatService] sendMessage - full state:', {
        selectedModel: selectedModel,
        availableModels: availableModels,
        storeKeys: Object.keys(useUIStore.getState())
      })
      
      // Use selected model, or first available, or fallback to qwen3.5:9b
      const model = selectedModel || availableModels[0] || 'qwen3.5:9b'
      
      console.log('[ChatService] Model selected:', model, '(selected=', selectedModel, ', firstAvailable=', availableModels[0], ')')
      
      const payload = {
        message_id: this.state.messageId,
        message: content,
        model: model,
      }
      
      console.log('[ChatService] Sending payload:', payload)

      console.log('[ChatService] Sending payload:', payload)
      this.ws?.send(JSON.stringify(payload))
    } catch (err) {
      console.error('[ChatService] Failed to send message:', err)
      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Connection failed',
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

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    events.emit('status', { status: 'idle' })
  }

  private async fallback() {
    try {
      const res = await fetch(
        'http://localhost:8000/api/chat',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: this.state.content,
            model: useUIStore.getState().selectedModel,
          }),
        }
      )

      const data = await res.json()

      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.result,
        status: 'done',
      })
    } catch {
      this.emit({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Connection failed',
        status: 'error',
      })
    }

    events.emit('status', { status: 'idle' })
  }
}

export const chatService = new ChatService()