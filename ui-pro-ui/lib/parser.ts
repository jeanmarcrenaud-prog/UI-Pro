// lib/parser.ts
/**
 * LLM Response Parser with Provider Adapter Architecture
 * Supports: Custom (UI-Pro), OpenAI, Anthropic, Grok, Mistral, Ollama
 */

export type LLMProvider = 'custom' | 'openai' | 'anthropic' | 'grok' | 'mistral' | 'ollama'

export interface ILlmResponse {
  type?: string
  delta?: unknown
  content?: unknown
  response?: unknown
  data?: unknown
  text?: unknown
  choices?: Array<{
    delta?: { content?: string }
    message?: { content?: string }
    finish_reason?: string
  }>
  done?: boolean
  finish_reason?: string
  stop_reason?: string
  done_reason?: string
  [key: string]: unknown
}

export interface IDeltaExtractor {
  extractDelta(parsed: unknown): string
  isDone(parsed: unknown): boolean
}

export interface IProviderAdapter extends IDeltaExtractor {
  readonly provider: LLMProvider
  canHandle(parsed: unknown): boolean
}

// ==================== BASE ADAPTER ====================

abstract class BaseAdapter implements IProviderAdapter {
  abstract readonly provider: LLMProvider

  canHandle(_parsed: unknown): boolean {
    return false
  }

  extractDelta(parsed: unknown): string {
    if (!parsed || typeof parsed !== 'object') return ''
    return this.extractFromObject(parsed as Record<string, unknown>)
  }

  isDone(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    return this.checkDoneSignal(parsed as Record<string, unknown>)
  }

  protected extractFromObject(p: Record<string, unknown>): string {
    // 1. Custom protocol (highest priority inside base)
    if (p.type === 'token' && typeof p.data === 'string') return p.data
    if (typeof p.response === 'string') return p.response
    if (typeof p.content === 'string') return p.content
    if (typeof p.data === 'string') return p.data
    if (typeof p.text === 'string') return p.text
    if (typeof p.delta === 'string') return p.delta

    // 2. OpenAI-style
    if (Array.isArray(p.choices)) {
      const choice = p.choices[0] as Record<string, unknown> | undefined
      if (choice?.delta?.content) return String(choice.delta.content)
      if (choice?.message?.content) return String(choice.message.content)
    }

    // 3. Anthropic-style
    if (p.delta && typeof p.delta === 'object') {
      const d = p.delta as Record<string, unknown>
      if (d.text) return String(d.text)
      if ((d.delta as Record<string, unknown>)?.text) return String((d.delta as Record<string, unknown>).text)
    }

    if (Array.isArray(p.content) && (p.content[0] as Record<string, unknown>)?.text) {
      return String((p.content[0] as Record<string, unknown>).text)
    }

    return ''
  }

  protected checkDoneSignal(p: Record<string, unknown>): boolean {
    if (p.done === true) return true
    if (p.type === 'done') return true
    if (p.type === 'message_stop') return true
    if (p.finish_reason || p.stop_reason || p.done_reason) return true

    if (Array.isArray(p.choices)) {
      return !!(p.choices[0] as Record<string, unknown>)?.finish_reason
    }

    return false
  }
}

// ==================== CONCRETE ADAPTERS ====================

class CustomProtocolAdapter extends BaseAdapter {
  readonly provider = 'custom' as const

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    return typeof p.type === 'string' && 
           ['token', 'step', 'done', 'error', 'cancelled', 'pong'].includes(p.type)
  }

  protected extractFromObject(p: Record<string, unknown>): string {
    if (p.type === 'token') return String(p.data || p.content || '')
    return ''
  }

  protected checkDoneSignal(p: Record<string, unknown>): boolean {
    return p.type === 'done' || p.done === true || p.type === 'cancelled'
  }
}

class OpenAIAdapter extends BaseAdapter {
  readonly provider = 'openai' as const

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    return Array.isArray(p.choices) || 
           p.object === 'chat.completion.chunk' ||
           p.object === 'chat.completion'
  }
}

class AnthropicAdapter extends BaseAdapter {
  readonly provider = 'anthropic' as const

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    return p.type === 'message_delta' || 
           p.type === 'content_block_delta' || 
           p.type === 'message_stop' ||
           Array.isArray(p.content)
  }
}

class OllamaAdapter extends BaseAdapter {
  readonly provider = 'ollama' as const

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    return 'response' in p || p.done !== undefined || 
           (typeof p.model === 'string' && p.model.includes('ollama'))
  }

  protected extractFromObject(p: Record<string, unknown>): string {
    return String(p.response || p.content || '')
  }
}

// Grok and Mistral mostly follow OpenAI format
class GrokAdapter extends OpenAIAdapter {
  readonly provider = 'grok' as const
}

class MistralAdapter extends OpenAIAdapter {
  readonly provider = 'mistral' as const
}

// ==================== REGISTRY & FACTORY ====================

const adapters: IProviderAdapter[] = [
  new CustomProtocolAdapter(),   // Highest priority
  new OpenAIAdapter(),
  new AnthropicAdapter(),
  new OllamaAdapter(),
  new GrokAdapter(),
  new MistralAdapter(),
]

export function detectAndGetAdapter(parsed: unknown): IProviderAdapter {
  for (const adapter of adapters) {
    if (adapter.canHandle(parsed)) {
      return adapter
    }
  }
  return adapters[0] // fallback to custom
}

export function getAdapter(provider: LLMProvider): IProviderAdapter | undefined {
  return adapters.find(a => a.provider === provider)
}

// ==================== PUBLIC API ====================

export function extractDelta(parsed: unknown): string {
  return detectAndGetAdapter(parsed).extractDelta(parsed)
}

export function isDone(parsed: unknown): boolean {
  return detectAndGetAdapter(parsed).isDone(parsed)
}

// For advanced usage
export { BaseAdapter, CustomProtocolAdapter, OpenAIAdapter, AnthropicAdapter, OllamaAdapter }