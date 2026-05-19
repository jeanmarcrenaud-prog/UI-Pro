// domain/events/StreamEvents.ts
// Role: Stream event type constants - core event types for the streaming layer

export const STREAM_EVENTS = {
  TOKEN: 'token',
  STEP: 'step',
  TOOL: 'tool',
  DONE: 'done',
  ERROR: 'error',
  CANCELLED: 'cancelled',
} as const;

export type StreamEventType = (typeof STREAM_EVENTS)[keyof typeof STREAM_EVENTS];
