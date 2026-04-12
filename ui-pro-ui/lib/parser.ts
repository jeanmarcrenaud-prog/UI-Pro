export function extractDelta(parsed: any): string {
  if (!parsed) return ''

  if (parsed.type === 'token') return parsed.data || ''
  if (parsed.delta) return parsed.delta
  if (parsed.text) return parsed.text
  if (parsed.content) return parsed.content
  if (parsed.result) return parsed.result

  return ''
}
