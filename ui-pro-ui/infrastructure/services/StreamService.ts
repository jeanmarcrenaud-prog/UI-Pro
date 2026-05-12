// infrastructure/services/StreamService.ts
/**
 * Streaming Service Abstraction
 * Normalizes backend StreamChunk → frontend StreamEvent
 */

import { STREAM_EVENTS } from '@/domain/events';

export interface BackendStreamChunk {
  type: string;
  status?: string;
  stream_id?: string;
  index?: number;
  data?: string;
  content?: string;
  response?: string;
  tokens?: number;
  tokens_generated?: number;
  latency_ms?: number;
  error?: string;
  step_id?: string;
  step_status?: string;
  timestamp?: string;
}

export interface StreamEvent {
  type: 'token' | 'step' | 'tool' | 'done' | 'error' | 'cancelled';
  content: string;
  index?: number;
  tokens?: number;
  tokensGenerated?: number;
  error?: string;
  stepId?: string;
  stepStatus?: string;
  streamId?: string;
  latencyMs?: number;
}

export interface StreamOptions {
  onChunk?: (event: StreamEvent) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
  onCancelled?: () => void;
  temperature?: number;
}

class StreamService {
  private eventSource: EventSource | null = null;
  private ws: WebSocket | null = null;
  private currentStreamId: string | null = null;

  private handlers: Required<StreamOptions> = {
    onChunk: () => {},
    onDone: () => {},
    onError: () => {},
    onCancelled: () => {},
    temperature: 0.7,
  };

  on(handler: (event: StreamEvent) => void): () => void {
    const original = this.handlers.onChunk;
    this.handlers.onChunk = (event) => {
      original(event);
      handler(event);
    };
    return () => {
      this.handlers.onChunk = original;
    };
  }

  onEvent(handler: (event: StreamEvent) => void): () => void {
    return this.on(handler);
  }

  async connect(content: string, model?: string): Promise<void> {
    return this.startStream(content, model || 'llama3', this.handlers);
  }

  async startStream(
    prompt: string,
    model: string,
    options: Partial<StreamOptions> = {}
  ): Promise<void> {
    this.close();
    this.handlers = { ...this.handlers, ...options };

    const url = this.buildStreamUrl(prompt, model, options.temperature);
    this.eventSource = new EventSource(url.toString());

    this.eventSource.onmessage = (event) => {
      try {
        const data: BackendStreamChunk = JSON.parse(event.data);
        const normalized = this.normalizeChunk(data);
        this.dispatchEvent(normalized);
      } catch (err) {
        this.handlers.onChunk({
          type: 'token',
          content: event.data,
        });
      }
    };

    this.eventSource.onerror = (err) => {
      console.error('[StreamService] SSE Error:', err);
      this.handlers.onError(new Error('Stream connection error'));
      this.close();
    };

    this.eventSource.onopen = () => {
      console.log('[StreamService] Stream connected');
    };
  }

  private buildStreamUrl(prompt: string, model: string, temperature?: number): URL {
    const url = new URL('/api/stream', window.location.origin);
    url.searchParams.set('prompt', prompt);
    url.searchParams.set('model', model);
    if (temperature !== undefined) {
      url.searchParams.set('temperature', temperature.toString());
    }
    return url;
  }

  private normalizeChunk(data: BackendStreamChunk): StreamEvent {
    const content = data.response || data.content || data.data || '';

    if (data.type === 'step' || data.step_id) {
      return {
        type: 'step',
        content: '',
        stepId: data.step_id,
        stepStatus: data.step_status,
        streamId: data.stream_id,
      };
    }

    if (data.status === 'completed' || data.type === 'done') {
      return { type: 'done', content };
    }

    if (data.status === 'error' || data.type === 'error') {
      return {
        type: 'error',
        content: '',
        error: data.error || 'Unknown error occurred',
      };
    }

    if (data.type === 'cancelled' || data.status === 'cancelled') {
      return { type: 'cancelled', content: '' };
    }

    return {
      type: 'token',
      content,
      index: data.index,
      tokens: data.tokens,
      tokensGenerated: data.tokens_generated,
      streamId: data.stream_id,
      latencyMs: data.latency_ms,
    };
  }

  private dispatchEvent(event: StreamEvent): void {
    if (event.type === 'done') {
      this.handlers.onDone();
    } else if (event.type === 'error') {
      this.handlers.onError(new Error(event.error || 'Stream error'));
    } else if (event.type === 'cancelled') {
      this.handlers.onCancelled();
    } else {
      this.handlers.onChunk(event);
    }
  }

  async cancelCurrentStream(): Promise<void> {
    if (!this.currentStreamId) return;

    try {
      await fetch('/api/stream/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream_id: this.currentStreamId }),
      });
    } catch (e) {
      console.warn('[StreamService] Failed to cancel stream:', e);
    }

    this.close();
  }

  close(): void {
    this.eventSource?.close();
    this.ws?.close();
    this.eventSource = null;
    this.ws = null;
    this.currentStreamId = null;
  }
}

export const streamService = new StreamService();
export const createStreamService = (options?: StreamOptions) => new StreamService();

export type {
  StreamEvent as IStreamEvent,
  BackendStreamChunk as IBackendChunk,
  StreamOptions as IStreamOpts,
};
