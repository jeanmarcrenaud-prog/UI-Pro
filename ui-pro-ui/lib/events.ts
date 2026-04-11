// Event Emitter - Simple event-driven architecture
type EventHandler<T = unknown> = (data: T) => void

interface EventMap {
  // Chat events
  message: { role: 'user' | 'assistant'; content: string }
  status: { status: 'idle' | 'connecting' | 'streaming' | 'error' }
  
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

  // Clear all handlers (for cleanup)
  clear(): void {
    this.handlers.clear()
  }
}

export const events = new EventEmitter()