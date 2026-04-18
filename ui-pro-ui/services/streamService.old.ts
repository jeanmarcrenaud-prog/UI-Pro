// Stream Service - Real-time streaming with events
import { events } from '@/lib/events'

type StreamEvent = {
  type: 'token' | 'step' | 'tool' | 'done' | 'error' | 'tokens'
  data: string
  stepId?: string
  toolName?: string
  tokenCount?: number
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
        // Debug: log all incoming messages
        console.log('[STREAM] Received:', data.substring(0, 100))

        // Skip empty
        if (!data || !data.trim()) return

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

        // Handle plain text (from backend using print())
        // Try JSON parse first, if fail use as plain token
        let tokenData = data
        let tokenCount: number | undefined
        try {
          const parsed = JSON.parse(data)
          
          // Handle step events
          if (parsed.type === 'step') {
            const streamEvent: StreamEvent = {
              type: 'step',
              data: parsed.status || 'pending',
              stepId: parsed.step_id,
            }
            this.emit(streamEvent)
            return
          }
          
          // Extract tokens count if present
          if (parsed.tokens !== undefined) {
            tokenCount = parsed.tokens
            this.emit({ type: 'tokens', data: '', tokenCount })
          }
          if (parsed.content) tokenData = parsed.content
          else if (parsed.message) tokenData = parsed.message
          else if (parsed.text) tokenData = parsed.text
          else if (parsed.result) tokenData = parsed.result
        } catch {
          // Plain text - use as-is
          tokenData = data
        }

        // Regular token
        this.emit({ type: 'token', data: tokenData })
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
        // Try JSON parse first
        let tokenData = data.result || ''
        if (data.content) tokenData = data.content
        else if (data.message) tokenData = data.message
        else if (data.text) tokenData = data.text
        this.emit({ type: 'token', data: tokenData })
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
            // Try JSON parse first
            let tokenData = line
            try {
              const parsed = JSON.parse(line)
              if (parsed.content) tokenData = parsed.content
              else if (parsed.message) tokenData = parsed.message
              else if (parsed.text) tokenData = parsed.text
              else if (parsed.result) tokenData = parsed.result
            } catch {
              // Plain text - use as-is
              tokenData = line
            }
            this.emit({ type: 'token', data: tokenData })
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