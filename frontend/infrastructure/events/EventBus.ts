// infrastructure/events/EventBus.ts
// Role: Central event bus implementation - type-safe pub/sub for app-wide events

import type { EventMap, AnyEventHandler, EventHandler } from '@/domain/events';

export const STREAM_EVENTS = {
  TOKEN: 'token',
  STEP: 'step',
  TOOL: 'tool',
  DONE: 'done',
  ERROR: 'error',
  CANCELLED: 'cancelled',
} as const;

export type StreamEventType = (typeof STREAM_EVENTS)[keyof typeof STREAM_EVENTS];

export class EventEmitter {
  private handlers = new Map<string, Set<AnyEventHandler>>();

  on<K extends keyof EventMap>(event: K, handler: EventHandler<EventMap[K]>): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set());
    }
    this.handlers.get(event)!.add(handler as AnyEventHandler);
  }

  off<K extends keyof EventMap>(event: K, handler: EventHandler<EventMap[K]>): void {
    this.handlers.get(event)?.delete(handler as AnyEventHandler);
  }

  emit<K extends keyof EventMap>(event: K, data: EventMap[K]): void {
    if (process.env.NODE_ENV === 'development') {
      console.log('[events.emit]', event, data);
    }
    this.handlers.get(event)?.forEach((handler) => {
      try {
        handler(data);
      } catch (err) {
        console.error(`[events] Handler error on ${String(event)}:`, err);
      }
    });
  }

  clear(): void {
    this.handlers.clear();
  }
}

export const events = new EventEmitter();
