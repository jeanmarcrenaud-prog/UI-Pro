// Event Emitter - Simple event-driven architecture
type EventHandler<T = unknown> = (data: T) => void

interface EventMap {
  message: { role: 'user' | 'assistant'; content: string }
  status: { status: 'idle' | 'connecting' | 'streaming' | 'error' }
  agentStep: { stepId: string; status: 'pending' | 'active' | 'done' }
  modelChange: { model: string }
  error: { message: string }
}

class EventEmitter {
  private handlers: Map<string, Set<EventHandler>> = new Map()

  on<K extends keyof EventMap>(event: K, handler: EventHandler<EventMap[K]>): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set())
    }
    this.handlers.get(event)!.add(handler)
  }

  off<K extends keyof EventMap>(event: K, handler: EventHandler<EventMap[K]>): void {
    this.handlers.get(event)?.delete(handler)
  }

  emit<K extends keyof EventMap>(event: K, data: EventMap[K]): void {
    this.handlers.get(event)?.forEach((handler) => handler(data))
  }
}

export const events = new EventEmitter()