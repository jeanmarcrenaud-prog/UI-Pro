// Stream Service - Real-time streaming with events
import { events } from '@/lib/events'

type StreamEvent = {
  type: 'token' | 'step' | 'tool' | 'done' | 'error'
  data: string
  stepId?: string
  toolName?: string
}

type StreamHandler = (event: StreamEvent) => void

class StreamService {
  private ws: WebSocket | null = null
  private handlers: Set<StreamHandler> = new Set()
  private baseUrl: string

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl
  }

  onEvent(handler: StreamHandler) {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  async connect(message: string): Promise<void> {
    // Close existing connection
    this.disconnect()

    events.emit('status', { status: 'connecting' })

    try {
      const wsUrl = `ws://${window.location.hostname}:8000/ws`
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        events.emit('status', { status: 'streaming' })
        this.ws?.send(JSON.stringify({ message }))
      }

      this.ws.onmessage = (event) => {
        const data = event.data

        // Parse stream events
        if (data.startsWith('[STEP]')) {
          const stepData = data.slice(6).split(':')
          const streamEvent: StreamEvent = {
            type: 'step',
            data: stepData[1] || '',
            stepId: stepData[0],
          }
          this.emit(streamEvent)
          return
        }

        if (data.startsWith('[TOOL]')) {
          const toolData = data.slice(6).split(':')
          const streamEvent: StreamEvent = {
            type: 'tool',
            data: toolData[1] || '',
            toolName: toolData[0],
          }
          this.emit(streamEvent)
          return
        }

        if (data === '[DONE]') {
          this.emit({ type: 'done', data: '' })
          events.emit('status', { status: 'idle' })
          this.disconnect()
          return
        }

        // Regular token
        this.emit({ type: 'token', data })
      }

      this.ws.onerror = () => {
        this.fallbackFetch(message)
      }

      this.ws.onclose = () => {
        events.emit('status', { status: 'idle' })
      }
    } catch {
      this.fallbackFetch(message)
    }
  }

  private async fallbackFetch(message: string): Promise<void> {
    events.emit('status', { status: 'connecting' })

    try {
      const response = await fetch(`${this.baseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      })

      const reader = response.body?.getReader()
      if (!reader) {
        // No streaming - just get full response
        const data = await response.json()
        this.emit({ type: 'token', data: data.result || '' })
        this.emit({ type: 'done', data: '' })
        events.emit('status', { status: 'idle' })
        return
      }

      // Read streaming response
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          this.emit({ type: 'done', data: '' })
          events.emit('status', { status: 'idle' })
          break
        }
        const text = decoder.decode(value, { stream: true })
        // Split by newlines for individual tokens
        text.split('\n').forEach(line => {
          if (line.trim()) {
            this.emit({ type: 'token', data: line })
          }
        })
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Connection failed'
      this.emit({ type: 'error', data: errorMsg })
      events.emit('status', { status: 'error' })
    }
  }

  private emit(event: StreamEvent) {
    // Emit to handlers
    this.handlers.forEach(handler => handler(event))
    // Also emit to global events
    if (event.type === 'token') {
      events.emit('message', { role: 'assistant', content: event.data })
    } else if (event.type === 'step') {
      events.emit('agentStep', { stepId: event.stepId || '', status: event.data as 'pending' | 'active' | 'done' })
    } else if (event.type === 'tool') {
      events.emit('toolCall', { tool: event.toolName || '', status: event.data as 'start' | 'done' })
    }
  }

  disconnect() {
    this.ws?.close()
    this.ws = null
  }
}

export const streamService = new StreamService()