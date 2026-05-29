// providers/llamacpp.ts
// Role: llama.cpp model discovery provider (uses Ollama-compatible API)

import { Model, estimateMaxContext, estimateSpeed, isCoder, isReasoning, isVision, inferCapabilities } from './helpers'

export async function fetchLlamaCpp(url: string): Promise<Model[]> {
  // llama.cpp uses Ollama-compatible API (/api/tags)
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)

  try {
    // Try Ollama-compatible endpoint first
    const response = await fetch(`${url}/api/tags`, {
      method: 'GET',
      signal: controller.signal,
    })

    if (!response.ok) return []

    const data = await response.json()
    // llama.cpp returns same format as Ollama - treat as "ollama"
    return (data.models || []).map((m: { name: string; size?: number; details?: Record<string, unknown> }) => {
      const details = m.details || {}
      const paramSize = details.parameter_size as string | undefined
      const quant = details.quantization_level as string | undefined
      const family = details.family as string | undefined
      const sizeBytes = m.size || 0

      return {
        id: m.name,
        name: m.name,
        provider: 'ollama' as const,
        parameterSize: paramSize,
        quantization: quant,
        sizeGb: sizeBytes > 0 ? Math.round(sizeBytes / 1024 / 1024 / 1024 * 100) / 100 : undefined,
        family: family,
        maxContext: estimateMaxContext(paramSize || '', family || ''),
        speedTier: estimateSpeed(quant || '', paramSize || ''),
        isCoder: isCoder(m.name),
        isReasoning: isReasoning(m.name),
        isVision: isVision(m.name),
        capabilities: inferCapabilities(m.name, paramSize || '', family || ''),
      }
    })
  } catch {
    return []
  } finally {
    clearTimeout(timeout)
  }
}
