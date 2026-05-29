// providers/ollama.ts
// Role: Ollama model discovery provider

import { Model, estimateMaxContext, estimateSpeed, isCoder, isReasoning, isVision, inferCapabilities } from './helpers'

export async function fetchOllama(url: string): Promise<Model[]> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 3000)

  let response: Response
  try {
    response = await fetch(`${url}/api/tags`, {
      method: 'GET',
      signal: controller.signal,
    })
  } catch {
    // Fallback to proxy backend for model discovery
    try {
      const proxyController = new AbortController()
      const proxyTimeout = setTimeout(() => proxyController.abort(), 3000)
      response = await fetch('/api/settings/default-model', {
        method: 'GET',
        signal: proxyController.signal,
      })
      clearTimeout(proxyTimeout)
    } catch {
      return []
    }
  } finally {
    clearTimeout(timeout)
  }

  if (!response.ok) return []

  const data = await response.json()

  // Handle both direct ollama format and proxy format
  if (data.models) {
    return data.models.map((m: { name: string; size?: number; details?: Record<string, unknown> }) => {
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
  }
  // Proxy returned { model_fast: ... } - not a model list
  return []
}
