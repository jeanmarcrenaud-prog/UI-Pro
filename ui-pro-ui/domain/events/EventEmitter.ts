// domain/events/EventEmitter.ts
import { type EventHandler, type EventMap, AnyEventHandler } from './EventTypes'

export class EventEmitter<K extends keyof EventMap = keyof EventMap> {
  private handlers = new Map<string, Set<AnyEventHandler>>()

  on<E extends K>(event: E, handler: EventHandler<EventMap[E]>): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set())
    }
    this.handlers.get(event)!.add(handler as AnyEventHandler)
  }

  off<E extends K>(event: E, handler: EventHandler<EventMap[E]>): void {
    this.handlers.get(event)?.delete(handler as AnyEventHandler)
  }

  emit<E extends K>(event: E, data: EventMap[E]): void {
    this.handlers.get(event)?.forEach((handler) => {
      try {
        handler(data)
      } catch (err) {
        console.error(`[events] Handler error on ${String(event)}:`, err)
      }
    })
  }

  clear(): void {
    this.handlers.clear()
  }
}
