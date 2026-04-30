// streamService.ts
// Role: Streaming service abstraction - normalizes SSE/WS events to StreamEvent shape
// Aligns with backend StreamChunk structure

import { STREAM_EVENTS } from '@/lib/events'

// Backend StreamChunk structure (from Python backend)
export interface BackendStreamChunk {
  type: string
  status?: string
  stream_id?: string
  index?: number
  data?: string
  content?: string
  response?: string
  tokens?: number
  error?: string
  step_id?: string
  step_status?: string
}

// Normalized frontend stream event
export interface StreamEvent {
  type: 'token' | 'step' | 'tool' | 'done' | 'error' | 'cancelled'
  content: string
  index?: number
  tokens?: number
  error?: string
  stepId?: string
  stepStatus?: string
  streamId?: string
}

export interface StreamServiceOptions {
  onChunk?: (event: StreamEvent) => void
  onDone?: () => void
  onError?: (error: Error) => void
  onCancelled?: () => void
}

class StreamService {
  private eventSource: EventSource | null = null
  private ws: WebSocket | null = null

  // Callbacks
  private handlers: StreamServiceOptions = {}

  constructor(options?: StreamServiceOptions) {
    this.handlers = options || {}
  }

  setHandlers(handlers: Partial<StreamServiceOptions>) {
    Object.assign(this.handlers, handlers)
  }

  async startStream(prompt: string, model?: string, options?: { temperature?: number }) {
    // Prefer SSE for streaming
    const url = new URL('/api/stream', window.location.origin)
    url.searchParams.set('prompt', prompt)
    if (model) url.searchParams.set('model', model)
    if (options?.temperature) url.searchParams.set('temperature', options.temperature.toString())

    this.eventSource = new EventSource(url.toString())

    this.eventSource.onmessage = (e) => {
      try {
        const data: BackendStreamChunk = JSON.parse(e.data)
        const normalized = this.normalizeChunk(data)

        if (normalized.type === 'done') {
          this.handlers.onDone?.()
        } else if (normalized.type === 'error') {
          this.handlers.onError?.(new Error(normalized.error))
        } else if (normalized.type === 'cancelled') {
          this.handlers.onCancelled?.()
        } else {
          this.handlers.onChunk?.(normalized)
        }
      } catch {
        // Non-JSON fallback - treat as token
        this.handlers.onChunk?.({
          type: 'token',
          content: e.data,
        })
      }
    }

    this.eventSource.onerror = () => {
      this.handlers.onError?.(new Error('Stream connection failed'))
    }
  }

  // Normalize backend chunk to frontend event
  private normalizeChunk(data: BackendStreamChunk): StreamEvent {
    // Handle step events
    if (data.type === STREAM_EVENTS.STEP || data.step_id) {
      return {
        type: 'step',
        content: '',
        stepId: data.step_id,
        stepStatus: data.step_status,
        streamId: data.stream_id,
      }
    }

    // Handle tool events
    if (data.type === STREAM_EVENTS.TOOL) {
      return {
        type: 'tool',
        content: data.data || '',
      }
    }

    // Handle terminal states
    if (data.status === 'completed' || data.type === STREAM_EVENTS.DONE) {
      return { type: 'done', content: data.response || '' }
    }

    if (data.status === 'error' || data.type === STREAM_EVENTS.ERROR) {
      return { type: 'error', content: '', error: data.error }
    }

    if (data.type === STREAM_EVENTS.CANCELLED) {
      return { type: 'cancelled', content: '' }
    }

    // Default: token content
    return {
      type: 'token',
      content: data.response || data.content || data.data || '',
      index: data.index,
      tokens: data.tokens,
      streamId: data.stream_id,
    }
  }

  close() {
    this.eventSource?.close()
    this.ws?.close()
    this.eventSource = this.ws = null
  }
}

// Singleton for app-wide streaming
export const streamService = new StreamService()

// Export factory and types
export const createStreamService = (options?: StreamServiceOptions) => new StreamService(options)

export type {
  StreamServiceOptions as StreamOpts,
  BackendStreamChunk as BackendChunk,
  StreamEvent as StreamMsg
}