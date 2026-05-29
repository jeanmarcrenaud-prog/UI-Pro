// providers/lmstudio.ts
// Role: LM Studio model discovery provider

import { Model, estimateSpeed, isCoder, isReasoning, isVision, inferCapabilities } from './helpers'

export async function fetchLMStudio(url: string): Promise<Model[]> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)

  try {
    // LM Studio uses /api/v1/models endpoint
    const response = await fetch(`${url}/api/v1/models`, {
      method: 'GET',
      signal: controller.signal,
    })

    if (!response.ok) return []

    const data = await response.json()
    // LM Studio returns { models: [...] } with rich metadata
    return (data.models || []).map((m: {
      key: string
      display_name?: string
      architecture?: string
      quantization?: { name?: string; bits_per_weight?: number }
      size_bytes?: number
      params_string?: string
      max_context_length?: number
    }) => {
      const quant = m.quantization?.name
      const paramSize = m.params_string || ''
      const sizeBytes = m.size_bytes || 0

      return {
        id: m.key,
        name: m.display_name || m.key,
        provider: 'lmstudio' as const,
        parameterSize: paramSize || undefined,
        quantization: quant,
        sizeGb: sizeBytes > 0 ? Math.round(sizeBytes / 1024 / 1024 / 1024 * 100) / 100 : undefined,
        family: m.architecture,
        maxContext: m.max_context_length,
        speedTier: estimateSpeed(quant || '', paramSize),
        isCoder: isCoder(m.display_name || m.key),
        isReasoning: isReasoning(m.display_name || m.key),
        isVision: isVision(m.display_name || m.key),
        capabilities: inferCapabilities(m.display_name || m.key, paramSize, m.architecture || ''),
      }
    })
  } catch (e) {
    console.debug('[ModelDiscovery] LM Studio fetch failed:', e)
    return []
  } finally {
    clearTimeout(timeout)
  }
}
