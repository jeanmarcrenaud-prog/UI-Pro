// domain/events/EventTypes.ts
// Role: Core event types for pub/sub system - domain-level event map definition

export type EventHandler<T = unknown> = (data: T) => void;

export interface EventMap {
  // Chat events
  message: {
    role: 'user' | 'assistant';
    content: string;
  };
  status: {
    status: 'idle' | 'connecting' | 'streaming' | 'error' | 'reconnecting' | 'retrying';
  };

  // Agent events
  agentStep: { stepId: string; status: 'pending' | 'active' | 'done' };
  agentPlan: { steps: string[] };

  // Tool events
  toolCall: { tool: string; status: 'start' | 'done' };
  toolResult: { tool: string; result: string };

  // Model events
  modelChange: { model: string };
  modelsDiscovered: {
    models: Array<{
      id: string;
      name: string;
      provider: string;
    }>;
    errors?: string[];
  };
  error: { message: string };

  // Custom store events
  log: { message?: string };
  tokens: { tokenCount?: number };
}

export type AnyEventHandler = EventHandler<unknown>;
