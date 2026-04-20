// Event Emitter - Simple event-driven architecture
type EventHandler<T = unknown> = (data: T) => void

interface EventMap {
  // Chat events
  message: { role: 'user' | 'assistant'; content: string }
  status: { status: 'idle' | 'connecting' | 'streaming' | 'error' | 'reconnecting' | 'retrying' }
  
  // Agent events
  agentStep: { stepId: string; status: 'pending' | 'active' | 'done' }
  agentPlan: { steps: string[] }
  
  // Tool events
  toolCall: { tool: string; status: 'start' | 'done' }
  toolResult: { tool: string; result: string }
  
  // Model events
  modelChange: { model: string }
  modelsDiscovered: { models: Array<{ id: string; name: string; provider: string }> }
  error: { message: string }
  
  // Custom store events
  log: { message?: string }
  tokens: { tokenCount?: number }
}

type AnyEventHandler = EventHandler<unknown>

class EventEmitter {
  private handlers: Map<string, Set<AnyEventHandler>> = new Map()

  on<K extends keyof EventMap>(event: K, handler: EventHandler<EventMap[K]>): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set())
    }
    this.handlers.get(event)!.add(handler as AnyEventHandler)
  }

  off<K extends keyof EventMap>(event: K, handler: EventHandler<EventMap[K]>): void {
    this.handlers.get(event)?.delete(handler as AnyEventHandler)
  }

  emit<K extends keyof EventMap>(event: K, data: EventMap[K]): void {
    if (process.env.NODE_ENV === 'development') {
      console.log('[events.emit]', event, data)
    }
    
    this.handlers.get(event)?.forEach((handler) => {
      try {
        handler(data)
      } catch (err) {
        console.error(`[events] Handler error on ${String(event)}:`, err)
      }
    })
  }

  // Clear all handlers (for cleanup)
  clear(): void {
    this.handlers.clear()
  }
}

export const events = new EventEmitter()