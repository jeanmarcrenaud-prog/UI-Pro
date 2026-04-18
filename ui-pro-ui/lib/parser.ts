/**
 * Extract text content from various LLM response formats
 * Supports: OpenAI, Anthropic, Ollama, custom protocols, and streaming formats
 */
export function extractDelta(parsed: any): string {
  if (!parsed || typeof parsed !== 'object') return ''

  // 1. Custom protocol (type field)
  if (parsed.type === 'token') return parsed.data || ''
  if (parsed.delta) return typeof parsed.delta === 'string' ? parsed.delta : ''
  if (parsed.content) return parsed.content || ''
  if (parsed.text) return parsed.text || ''
  if (parsed.result) return parsed.result || ''

  // 2. OpenAI streaming (choices[0].delta)
  if (parsed.choices && Array.isArray(parsed.choices) && parsed.choices[0]?.delta?.content) {
    return parsed.choices[0].delta.content
  }
  // Full OpenAI response (choices[0].message.content)
  if (parsed.choices && Array.isArray(parsed.choices) && parsed.choices[0]?.message?.content) {
    return parsed.choices[0].message.content
  }

  // 3. Anthropic streaming (delta.text)
  if (parsed.delta?.type === 'content_block_delta' && parsed.delta.delta?.text) {
    return parsed.delta.delta.text
  }
  // Anthropic full (content[0].text)
  if (parsed.content && Array.isArray(parsed.content) && parsed.content[0]?.text) {
    return parsed.content[0].text
  }

  // 4. Ollama streaming (response)
  if (parsed.response) return parsed.response
  if (parsed.done) return '' // Ignore done markers

  // 5. Generic text fields
  if (parsed.message) return parsed.message
  if (parsed.output) return parsed.output
  if (parsed.answer) return parsed.answer

  return ''
}

/**
 * Check if this is a completion/done marker
 */
export function isDone(parsed: any): boolean {
  if (!parsed) return false
  return parsed.type === 'done' || 
    parsed.done === true || 
    parsed.choices?.[0]?.finish_reason !== undefined ||
    parsed.stop_reason !== undefined
}
