/**
 * Extract text content from various LLM response formats
 * Supports: OpenAI, Anthropic, Ollama, custom protocols, and streaming formats
 */
export function extractDelta(parsed: any): string {
  if (!parsed || typeof parsed !== 'object') return ''

  // 1. Custom protocol (type field) - highest priority
  if (parsed.type === 'token') return parsed.data || ''
  if (parsed.type === 'done') return ''
  if (parsed.type === 'step' || parsed.type === 'error') return ''

  // 2. Streaming format (single chunk extraction)
  if (parsed.delta) return typeof parsed.delta === 'string' ? parsed.delta : ''
  if (parsed.response) return parsed.response
  if (parsed.data) return parsed.data

  // 3. OpenAI streaming (choices format)
  if (parsed.choices && Array.isArray(parsed.choices) && parsed.choices[0]?.delta?.content) {
    return parsed.choices[0].delta.content
  }
  // Full OpenAI response
  if (parsed.choices && Array.isArray(parsed.choices) && parsed.choices[0]?.message?.content) {
    // Handle both streaming and complete responses
    const content = parsed.choices[0].message.content
    if (content) return content
  }

  // 4. Anthropic streaming/content blocks
  if (parsed.delta?.type === 'content_block_delta' && parsed.delta.delta?.text) {
    return parsed.delta.delta.text
  }
  // Anthropic full content blocks
  if (parsed.content && Array.isArray(parsed.content) && parsed.content[0]?.text) {
    return parsed.content[0].text
  }

  // 5. Generic text fields (fallback)
  if (parsed.content && typeof parsed.content === 'string') return parsed.content
  if (parsed.text) return parsed.text
  if (parsed.message) return parsed.message
  if (parsed.result) return parsed.result
  if (parsed.output) return parsed.output
  if (parsed.answer) return parsed.answer
  if (parsed.thinking) return parsed.thinking
  if (parsed.content_block) return parsed.content_block

  return ''
}

/**
 * Check if this is a completion/done marker
 */
export function isDone(parsed: any): boolean {
  if (!parsed) return false
  
  // 1. Explicit done markers
  if (parsed.type === 'done' || parsed.done === true) return true
  
  // 2. Finish/stop reason (backend signaling)
  if (parsed.choices?.[0]?.finish_reason) return true
  if (parsed.finish_reason) return true
  if (parsed.stop_reason) return true
  if (parsed.done === true) return true
  
  // 3. Empty result (implicit done for some backends)
  if (!parsed.choices && !parsed.content && !parsed.result && !parsed.message) return true
  
  return false
}

