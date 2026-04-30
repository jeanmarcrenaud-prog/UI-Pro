// services/streamService.ts
/**
 * Streaming Service Abstraction
 * Normalizes backend StreamChunk → frontend StreamEvent
 * Supports SSE (preferred) and WebSocket fallback
 */

import { STREAM_EVENTS } from '@/lib/events'

export interface BackendStreamChunk {
  type: string
  status?: string
  stream_id?: string
  index?: number
  data?: string
  content?: string
  response?: string
  tokens?: number
  latency_ms?: number
  error?: string
  step_id?: string
  step_status?: string
  timestamp?: string
}

export interface StreamEvent {
  type: 'token' | 'step' | 'tool' | 'done' | 'error' | 'cancelled'
  content: string
  index?: number
  tokens?: number
  error?: string
  stepId?: string
  stepStatus?: string
  streamId?: string
  latencyMs?: number
}

export interface StreamOptions {
  onChunk?: (event: StreamEvent) => void
  onDone?: () => void
  onError?: (error: Error) => void
  onCancelled?: () => void
  temperature?: number
}

class StreamService {
  private eventSource: EventSource | null = null
  private ws: WebSocket | null = null
  private currentStreamId: string | null = null

  private handlers: Required<StreamOptions> = {
    onChunk: () => {},
    onDone: () => {},
    onError: () => {},
    onCancelled: () => {},
    temperature: 0.7,
  }

  constructor() {
    // Singleton - no initial options
  }

  /**
   * Start a new streaming request
   */
  async startStream(
    prompt: string,
    model: string,
    options: Partial<StreamOptions> = {}
  ): Promise<void> {
    this.close() // Close any existing stream

    // Merge handlers
    this.handlers = { ...this.handlers, ...options }

    const url = this.buildStreamUrl(prompt, model, options.temperature)

    // Prefer SSE (simpler, auto-reconnect friendly)
    this.eventSource = new EventSource(url.toString())

    this.eventSource.onmessage = (event) => {
      try {
        const data: BackendStreamChunk = JSON.parse(event.data)
        const normalized = this.normalizeChunk(data)

        this.dispatchEvent(normalized)
      } catch (err) {
        // Fallback: raw text as token
        this.handlers.onChunk({
          type: 'token',
          content: event.data,
        })
      }
    }

    this.eventSource.onerror = (err) => {
      console.error('[StreamService] SSE Error:', err)
      this.handlers.onError(new Error('Stream connection error'))
      this.close()
    }

    this.eventSource.onopen = () => {
      console.log('[StreamService] Stream connected')
    }
  }

  private buildStreamUrl(prompt: string, model: string, temperature?: number): URL {
    const url = new URL('/api/stream', window.location.origin)

    url.searchParams.set('prompt', prompt)
    url.searchParams.set('model', model)
    if (temperature !== undefined) {
      url.searchParams.set('temperature', temperature.toString())
    }

    return url
  }

  /**
   * Normalize backend StreamChunk → clean frontend StreamEvent
   */
  private normalizeChunk(data: BackendStreamChunk): StreamEvent {
    const content = data.response || data.content || data.data || ''

    // Step event
    if (data.type === 'step' || data.step_id) {
      return {
        type: 'step',
        content: '',
        stepId: data.step_id,
        stepStatus: data.step_status,
        streamId: data.stream_id,
      }
    }

    // Terminal events
    if (data.status === 'completed' || data.type === 'done') {
      return { type: 'done', content }
    }

    if (data.status === 'error' || data.type === 'error') {
      return {
        type: 'error',
        content: '',
        error: data.error || 'Unknown error occurred',
      }
    }

    if (data.type === 'cancelled' || data.status === 'cancelled') {
      return { type: 'cancelled', content: '' }
    }

    // Default: token
    return {
      type: 'token',
      content,
      index: data.index,
      tokens: data.tokens,
      streamId: data.stream_id,
      latencyMs: data.latency_ms,
    }
  }

  private dispatchEvent(event: StreamEvent): void {
    if (event.type === 'done') {
      this.handlers.onDone()
    } else if (event.type === 'error') {
      this.handlers.onError(new Error(event.error || 'Stream error'))
    } else if (event.type === 'cancelled') {
      this.handlers.onCancelled()
    } else {
      this.handlers.onChunk(event)
    }
  }

  /**
   * Cancel current stream (if backend supports it)
   */
  async cancelCurrentStream(): Promise<void> {
    if (!this.currentStreamId) return

    try {
      await fetch('/api/stream/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream_id: this.currentStreamId }),
      })
    } catch (e) {
      console.warn('[StreamService] Failed to cancel stream:', e)
    }

    this.close()
  }

  /**
   * Close active connection
   */
  close(): void {
    this.eventSource?.close()
    this.ws?.close()

    this.eventSource = null
    this.ws = null
    this.currentStreamId = null
  }

  // For future WebSocket support
  private connectWebSocket() {
    // Implementation can be added later if needed for bidirectional features
    console.warn('[StreamService] WebSocket mode not yet implemented')
  }
}

// ====================== Exports ======================

export const streamService = new StreamService()

export const createStreamService = (options?: StreamOptions) => new StreamService()

export type {
  StreamEvent as IStreamEvent,
  BackendStreamChunk as IBackendChunk,
  StreamOptions as IStreamOpts,
}