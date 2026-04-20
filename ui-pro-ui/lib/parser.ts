/**
 * LLM Response Parser with Provider Adapter Architecture
 * Supports: Custom protocol, OpenAI, Anthropic, Grok, Mistral, Ollama
 * 
 * Type-safe extraction of streaming deltas and done signals from various LLM providers
 */

// ==================== TYPES ====================

/** Supported LLM providers */
export type LLMProvider = 'custom' | 'openai' | 'anthropic' | 'grok' | 'mistral' | 'ollama'

/** Generic LLM response shape */
export interface ILlmResponse {
  type?: string
  delta?: unknown
  data?: unknown
  content?: unknown
  response?: unknown
  choices?: Array<{
    delta?: { content?: string; role?: string }
    message?: { content?: string; role?: string }
    finish_reason?: string
    index?: number | string
  }>
  done?: boolean
  finish_reason?: string
  stop_reason?: string
  [key: string]: unknown
}

/** Delta extractor interface */
export interface IDeltaExtractor {
  extractDelta(parsed: unknown): string
  isDone(parsed: unknown): boolean
}

/** Provider adapter interface */
export interface IProviderAdapter extends IDeltaExtractor {
  readonly provider: LLMProvider
  canHandle(parsed: unknown): boolean
}

// ==================== BASE ADAPTER ====================

/** Abstract base adapter with common extraction logic */
abstract class BaseAdapter implements IProviderAdapter {
  abstract readonly provider: LLMProvider

  abstract canHandle(parsed: unknown): boolean

  extractDelta(parsed: unknown): string {
    if (!parsed || typeof parsed !== 'object') return ''
    const p = parsed as Record<string, unknown>
    return this.extractFromObject(p)
  }

  isDone(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    return this.checkDoneSignal(p)
  }

  /** Override in subclasses for custom extraction */
  protected extractFromObject(p: Record<string, unknown>): string {
    // Check custom protocol first
    if (p.type === 'token' && typeof p.data === 'string') return p.data
    if (p.type === 'done' || p.type === 'step' || p.type === 'error' || p.type === 'pong') return ''

    // Direct string fields
    if (typeof p.delta === 'string') return p.delta
    if (typeof p.response === 'string') return p.response
    if (typeof p.data === 'string') return p.data
    if (typeof p.content === 'string') return p.content
    if (typeof p.text === 'string') return p.text

    // OpenAI-style choices
    if (Array.isArray(p.choices)) {
      const choice = p.choices[0] as Record<string, unknown> | undefined
      if (choice?.delta && typeof choice.delta === 'object') {
        const delta = choice.delta as Record<string, unknown>
        if (typeof delta.content === 'string') return delta.content
      }
      if (choice?.message && typeof choice.message === 'object') {
        const msg = choice.message as Record<string, unknown>
        if (typeof msg.content === 'string') return msg.content
      }
    }

    // Anthropic-style
    if (p.delta && typeof p.delta === 'object') {
      const delta = p.delta as Record<string, unknown>
      if (delta.type === 'content_block_delta' && delta.delta && typeof delta.delta === 'object') {
        const blockDelta = delta.delta as Record<string, unknown>
        if (typeof blockDelta.text === 'string') return blockDelta.text
      }
    }

    if (Array.isArray(p.content) && p.content[0]) {
      const first = p.content[0] as Record<string, unknown>
      if (typeof first.text === 'string') return first.text
    }

    // Generic fallback
    const candidates = ['output', 'answer', 'result', 'thinking', 'completion', 'generated_text', 'message']
    for (const key of candidates) {
      if (typeof p[key] === 'string') return p[key]
    }

    return ''
  }

  /** Override in subclasses for custom done detection */
  protected checkDoneSignal(p: Record<string, unknown>): boolean {
    // Explicit done markers
    if (p.type === 'done' || p.done === true) return true

    // Finish reasons
    if (Array.isArray(p.choices)) {
      const choice = p.choices[0] as Record<string, unknown> | undefined
      if (choice?.finish_reason) return true
    }
    if (p.finish_reason || p.stop_reason) return true

    // Anthropic-style
    if (p.type === 'message_stop') return true

    // Pong/heartbeat
    if (p.type === 'pong') return true

    return false
  }
}

// ==================== CONCRETE ADAPTERS ====================

/** Custom protocol adapter (UI-Pro internal) */
class CustomProtocolAdapter extends BaseAdapter {
  readonly provider: LLMProvider = 'custom'

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    return typeof p.type === 'string' && ['token', 'step', 'done', 'error', 'pong'].includes(p.type)
  }

  protected extractFromObject(p: Record<string, unknown>): string {
    if (p.type === 'token' && typeof p.data === 'string') return p.data
    if (p.type === 'done' || p.type === 'step' || p.type === 'error' || p.type === 'pong') return ''
    if (typeof p.content === 'string') return p.content
    if (typeof p.data === 'string') return p.data
    return ''
  }

  protected checkDoneSignal(p: Record<string, unknown>): boolean {
    if (p.type === 'done' || p.done === true || p.type === 'pong') return true
    return false
  }
}

/** OpenAI API adapter */
class OpenAIAdapter extends BaseAdapter {
  readonly provider: LLMProvider = 'openai'

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    return Array.isArray(p.choices) || p.object === 'chat.completion' || p.object === 'chat.completion.chunk'
  }

  protected extractFromObject(p: Record<string, unknown>): string {
    if (!Array.isArray(p.choices)) return ''
    const choice = p.choices[0] as Record<string, unknown>

    // Streaming delta
    if (choice.delta && typeof choice.delta === 'object') {
      const delta = choice.delta as Record<string, unknown>
      if (typeof delta.content === 'string') return delta.content
    }

    // Full message
    if (choice.message && typeof choice.message === 'object') {
      const msg = choice.message as Record<string, unknown>
      if (typeof msg.content === 'string') return msg.content
    }

    return ''
  }

  protected checkDoneSignal(p: Record<string, unknown>): boolean {
    if (Array.isArray(p.choices)) {
      const choice = p.choices[0] as Record<string, unknown>
      if (choice?.finish_reason) return true
    }
    if (p.finish_reason) return true
    return false
  }
}

/** Anthropic API adapter */
class AnthropicAdapter extends BaseAdapter {
  readonly provider: LLMProvider = 'anthropic'

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    return p.type === 'message_delta' || 
           p.type === 'content_block_delta' || 
           Array.isArray(p.content) ||
           p.amazon_chunking_config !== undefined
  }

  protected extractFromObject(p: Record<string, unknown>): string {
    // Streaming: content_block_delta
    if (p.delta && typeof p.delta === 'object') {
      const delta = p.delta as Record<string, unknown>
      if (delta.type === 'content_block_delta' && delta.delta && typeof delta.delta === 'object') {
        const blockDelta = delta.delta as Record<string, unknown>
        if (typeof blockDelta.text === 'string') return blockDelta.text
      }
      // message_delta
      if (delta.text && typeof delta.text === 'string') return delta.text
    }

    // Full content blocks
    if (Array.isArray(p.content)) {
      const first = p.content[0] as Record<string, unknown>
      if (first?.text && typeof first.text === 'string') return first.text
    }

    return ''
  }

  protected checkDoneSignal(p: Record<string, unknown>): boolean {
    if (p.type === 'message_stop' || p.stop_reason) return true
    if (p.type === 'message_delta' && p.delta && typeof p.delta === 'object') {
      const delta = p.delta as Record<string, unknown>
      if (delta.stop_reason) return true
    }
    return false
  }
}

/** Grok (xAI) adapter */
class GrokAdapter extends BaseAdapter {
  readonly provider: LLMProvider = 'grok'

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    // Grok uses OpenAI-compatible format with xAI model field
    const isOpenAIFormat = Array.isArray(p.choices)
    const hasXAIField = 'x_grok' in p
    const modelIsGrok = typeof p.model === 'string' && p.model.startsWith('grok')
    return isOpenAIFormat || hasXAIField || modelIsGrok
  }

  // Uses base extraction - Grok is OpenAI-compatible
}

/** Mistral AI adapter */
class MistralAdapter extends BaseAdapter {
  readonly provider: LLMProvider = 'mistral'

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    const isOpenAIFormat = Array.isArray(p.choices)
    const modelIsMistral = typeof p.model === 'string' && p.model.includes('mistral')
    const hasMistralId = typeof p.id === 'string' && p.id.startsWith('mistral-')
    return isOpenAIFormat || modelIsMistral || hasMistralId
  }

  protected checkDoneSignal(p: Record<string, unknown>): boolean {
    // Mistral uses standard finish_reason
    if (Array.isArray(p.choices)) {
      const choice = p.choices[0] as Record<string, unknown>
      if (choice?.finish_reason === 'stop' || choice?.finish_reason === 'length') return true
    }
    if (p.finish_reason === 'stop' || p.finish_reason === 'length') return true
    return false
  }
}

/** Ollama local adapter */
class OllamaAdapter extends BaseAdapter {
  readonly provider: LLMProvider = 'ollama'

  canHandle(parsed: unknown): boolean {
    if (!parsed || typeof parsed !== 'object') return false
    const p = parsed as Record<string, unknown>
    // Ollama uses 'response' field and 'done' boolean
    return 'response' in p || 
           p.model?.toString().includes('ollama') ||
           p.created_at !== undefined
  }

  protected extractFromObject(p: Record<string, unknown>): string {
    // Ollama streaming: response field
    if (typeof p.response === 'string') return p.response
    
    // Ollama with message wrapper (newer API)
    if (p.message && typeof p.message === 'object') {
      const msg = p.message as Record<string, unknown>
      if (typeof msg.content === 'string') return msg.content
    }

    return ''
  }

  protected checkDoneSignal(p: Record<string, unknown>): boolean {
    if (p.done === true) return true
    if (p.done_reason === 'stop' || p.done_reason === 'length') return true
    return false
  }
}

// ==================== FACTORY ====================

/** Registry of all adapters */
const adapters: IProviderAdapter[] = [
  new CustomProtocolAdapter(),
  new OpenAIAdapter(),
  new AnthropicAdapter(),
  new GrokAdapter(),
  new MistralAdapter(),
  new OllamaAdapter(),
]

/** Get adapter for a specific provider */
export function getAdapter(provider: LLMProvider): IProviderAdapter | undefined {
  return adapters.find(a => a.provider === provider)
}

/** Auto-detect provider and return appropriate adapter */
export function detectAndGetAdapter(parsed: unknown): IProviderAdapter {
  for (const adapter of adapters) {
    if (adapter.canHandle(parsed)) {
      return adapter
    }
  }
  // Default to custom protocol adapter
  return adapters[0]
}

// ==================== LEGACY EXPORTS (backward compatibility) ====================

/**
 * Extract text delta/content from various LLM response formats.
 * Uses auto-detection to choose the right provider adapter.
 */
export function extractDelta(parsed: unknown): string {
  return detectAndGetAdapter(parsed).extractDelta(parsed)
}

/**
 * Detect completion/done signals.
 * Uses auto-detection to choose the right provider adapter.
 */
export function isDone(parsed: unknown): boolean {
  return detectAndGetAdapter(parsed).isDone(parsed)
}

// ==================== CONVENIENCE EXPORTS ====================

export { BaseAdapter }