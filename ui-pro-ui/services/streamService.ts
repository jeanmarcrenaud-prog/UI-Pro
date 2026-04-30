// streamService.ts
// Role: Streaming service abstraction - normalizes WebSocket/SSE events to StreamChunk-like shape
// Used by useStream hook

import { STREAM_EVENTS, type StreamEventType } from '@/lib/events'

export interface StreamChunk {
  type: StreamEventType
  content?: string
  step?: string
  tool?: string
  error?: string
  index?: number
}

export interface StreamServiceOptions {
  url: string
  mode?: 'websocket' | 'sse'
  onChunk?: (chunk: StreamChunk) => void
  onDone?: () => void
  onError?: (error: Error) => void
  onCancelled?: () => void
}

class StreamService {
  private url: string
  private mode: 'websocket' | 'sse'
  private eventSource: EventSource | null = null
  private ws: WebSocket | null = null
  private onChunk?: StreamChunk['type']
  private onDone?: () => void
  private onError?: (error: Error) => void
  private onCancelled?: () => void

  constructor(options: StreamServiceOptions) {
    this.url = options.url
    this.mode = options.mode || 'sse'
    this.onChunk = options.onChunk as StreamChunk['type']
    this.onDone = options.onDone
    this.onError = options.onError
    this.onCancelled = options.onCancelled
  }

  async connect(): Promise<void> {
    if (this.mode === 'sse') {
      await this.connectSSE()
    } else {
      await this.connectWS()
    }
  }

  private async connectSSE(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.eventSource = new EventSource(this.url)

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const chunk = this.mapToChunk(data)

          if (chunk) {
            if (chunk.type === STREAM_EVENTS.DONE) {
              this.onDone?.()
            } else if (chunk.type === STREAM_EVENTS.ERROR) {
              this.onError?.(new Error(chunk.error || 'Stream error'))
            } else if (chunk.type === STREAM_EVENTS.CANCELLED) {
              this.onCancelled?.()
            } else if (chunk.type === STREAM_EVENTS.TOKEN) {
              this.onChunk?.(chunk.type as StreamChunk['type'], chunk)
            }
          }
        } catch (err) {
          // Non-JSON response
          this.onChunk?.(STREAM_EVENTS.TOKEN as StreamChunk['type'], { type: STREAM_EVENTS.TOKEN as StreamChunk['type'], content: event.data })
        }
      }

      this.eventSource.onerror = () => {
        const err = new Error('SSE connection error')
        this.onError?.(err)
        reject(err)
      }

      this.eventSource.onopen = () => resolve()
    })
  }

  private async connectWS(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.url)

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const chunk = this.mapToChunk(data)

          if (chunk) {
            if (chunk.type === STREAM_EVENTS.DONE) {
              this.onDone?.()
            } else if (chunk.type === STREAM_EVENTS.ERROR) {
              this.onError?.(new Error(chunk.error || 'Stream error'))
            } else if (chunk.type === STREAM_EVENTS.CANCELLED) {
              this.onCancelled?.()
            } else if (chunk.type === STREAM_EVENTS.TOKEN) {
              this.onChunk?.(chunk.type as StreamChunk['type'], chunk)
            }
          }
        } catch {
          this.onChunk?.(STREAM_EVENTS.TOKEN as StreamChunk['type'], { type: STREAM_EVENTS.TOKEN as StreamChunk['type'], content: event.data })
        }
      }

      this.ws.onerror = () => {
        const err = new Error('WebSocket error')
        this.onError?.(err)
        reject(err)
      }

      this.ws.onopen = () => resolve()
    })
  }

  private mapToChunk(data: Record<string, unknown>): StreamChunk | null {
    const type = data.type as StreamEventType

    if (type === STREAM_EVENTS.TOKEN) {
      return { type: STREAM_EVENTS.TOKEN, content: data.content as string, index: data.index as number }
    }
    if (type === STREAM_EVENTS.STEP) {
      return { type: STREAM_EVENTS.STEP, step: data.step as string }
    }
    if (type === STREAM_EVENTS.TOOL) {
      return { type: STREAM_EVENTS.TOOL, tool: data.tool as string }
    }
    if (type === STREAM_EVENTS.DONE) {
      return { type: STREAM_EVENTS.DONE }
    }
    if (type === STREAM_EVENTS.ERROR) {
      return { type: STREAM_EVENTS.ERROR, error: data.error as string }
    }
    if (type === STREAM_EVENTS.CANCELLED) {
      return { type: STREAM_EVENTS.CANCELLED }
    }
    return null
  }

  send(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  close(): void {
    this.eventSource?.close()
    this.ws?.close()
    this.eventSource = null
    this.ws = null
  }
}

export function createStreamService(options: StreamServiceOptions): StreamService {
  return new StreamService(options)
}