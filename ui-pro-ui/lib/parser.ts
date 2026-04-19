/**
 * Extract text content from various LLM response formats
 * Supports: OpenAI, Anthropic, Ollama, custom protocols, and streaming formats
 */
export function extractDelta(parsed: any): string {
  if (!parsed || typeof parsed !== 'object') return ''

  // 1. Custom protocol (type field) - highest priority for event-driven protocols
  if (parsed.type === 'token') return parsed.data && typeof parsed.data === 'string' ? parsed.data : ''
  if (parsed.type === 'done') return ''
  if (parsed.type === 'step' || parsed.type === 'error' || parsed.type === 'pong') return ''

  // 2. Streaming event fields - only string values to avoid structured data
  if (parsed.delta && typeof parsed.delta === 'string') return parsed.delta
  if (parsed.delta && parsed.delta.text && typeof parsed.delta.text === 'string') return parsed.delta.text

  if (parsed.response && typeof parsed.response === 'string') return parsed.response
  if (parsed.data && typeof parsed.data === 'string') return parsed.data
  if (!parsed.data && typeof parsed.response !== 'string') return ''

  // 3. OpenAI streaming (choices format with streaming indication)
  if (parsed.choices && Array.isArray(parsed.choices) && parsed.choices[0]?.delta?.content) {
    // Streaming mode: single delta
    const delta = parsed.choices[0].delta.content
    if (delta && typeof delta === 'string') return delta
    // Full response mode: complete conversation (not streaming)
    // Skip extracting from full response in streaming context
  }
  // OpenAI full response (not streaming) - extract once
  if (parsed.choices && Array.isArray(parsed.choices) && parsed.choices[0]?.message?.content) {
    if (!parsed.type || parsed.type === 'token') {
      const content = parsed.choices[0].message.content
      if (content && typeof content === 'string') return content
    }
  }

  // 4. Anthropic streaming (content_block_delta)
  if (parsed.delta?.type === 'content_block_delta' && parsed.delta.delta?.text) {
    if (typeof parsed.delta.delta.text === 'string') return parsed.delta.delta.text
  }
  // Anthropic full content blocks
  if (parsed.content && Array.isArray(parsed.content) && parsed.content[0]?.text) {
    if (typeof parsed.content[0].text === 'string') return parsed.content[0].text
  }

  // 5. Generic text fields (only string types)
  const stringFields = ['content', 'text', 'message', 'result', 'output', 'answer', 'thinking', 'content_block']
  for (const field of stringFields) {
    if (parsed[field] && typeof parsed[field] === 'string') return parsed[field]
  }

  return ''
}

/**
 * Check if this is a completion/done marker
 * Must be called after streaming is complete or to detect intermediate done events
 */
export function isDone(parsed: any): boolean {
  if (!parsed) return false

  // 1. Explicit done markers
  if (parsed.type === 'done') return true
  if (parsed.done === true) return true

  // 2. Finish/stop reason from message completion
  if (parsed.choices?.[0]?.finish_reason) return true
  if (parsed.finish_reason) return true
  if (parsed.stop_reason) return true

  // 3. Pong/cleanup messages
  if (parsed.type === 'pong') return true

  // 4. NOT implicit done - don't prematurely end
  // Only treat as done if explicitly signaled
  // return parsed.choices && Array.isArray(parsed.choices) && !parsed.choices[0]?.delta // This would end prematurely

  return false
}
