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
    flush: null as any,
    stream: null as any,
    heartbeat: null as any,
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

  // =====================
  // STREAM HANDLER
  // =====================
  private handleMessage = (event: MessageEvent) => {
    console.log('[ChatService] Raw message:', event.data)
    try {
      const msg = JSON.parse(event.data)
      console.log('[ChatService] Parsed message:', msg)

      if (msg.type === 'pong') return

      if (msg.message_id && msg.message_id !== this.state.messageId)
        return

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

      const text = msg.content || msg.thinking

      if (text) {
        this.state.content += text
        this.state.buffer += text

        if (!this.timers.flush) {
          this.timers.flush = setTimeout(() => {
            this.flushBuffer()
            this.timers.flush = null
          }, 30)
        }
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
      console.warn('[ChatService] parse error')
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

      this.ws = new WebSocket(
        `ws://${window.location.hostname}:8000/ws`
      )

      this.ws.onopen = () => {
        console.log('[ChatService] WebSocket connected')
        resolve()
      }

      this.ws.onmessage = this.handleMessage

      this.ws.onclose = () => {
        this.clearTimers()

        if (this.state.reconnects < 3) {
          this.state.reconnects++
          setTimeout(() => this.connect(), 500 * this.state.reconnects)
        } else {
          this.stop()
        this.fallback()
      }
    }

    this.ws.onopen = () => {
      this.state.reconnects = 0

      this.timers.heartbeat = setInterval(() => {
        this.ws?.send(JSON.stringify({ type: 'ping' }))
      }, 15000)
    }
  }

  // =====================
  // PUBLIC API
  // =====================
  async sendMessage(content: string, messageId?: string) {
    this.resetState()
    this.state.messageId = messageId || crypto.randomUUID()

    await this.connect()

    const payload = {
      message_id: this.state.messageId,
      message: content,
      model: useUIStore.getState().selectedModel,
    }

    console.log('[ChatService] Sending payload:', payload)
    this.ws?.send(JSON.stringify(payload))
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