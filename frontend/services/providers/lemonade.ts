// providers/lemonade.ts
// Role: Lemonade model discovery provider

import { Model, estimateSpeed, isCoder, isReasoning, isVision, inferCapabilities } from './helpers'

export async function fetchLemonade(url: string): Promise<Model[]> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 5000)

  try {
    const response = await fetch(`${url}/api/v1/models`, {
      method: 'GET',
      signal: controller.signal,
    })

    if (!response.ok) {
      return []
    }

    const data = await response.json()
    // Lemonade returns { data: [...] } - extract what we can
    return (data.data || []).map((m: {
      id: string
      labels?: string[]
      size?: number
    }) => {
      const name = m.id
      const nameLower = name.toLowerCase()

      // Try to extract parameter size from name or labels
      let paramSize = ''
      if (m.labels) {
        const sizeLabel = m.labels.find(l => l.match(/\d+b/i))
        if (sizeLabel) paramSize = sizeLabel
      }

      return {
        id: m.id,
        name: m.id,
        provider: 'lemonade' as const,
        parameterSize: paramSize || undefined,
        sizeGb: m.size ? Math.round(m.size / 1024 / 1024 / 1024 * 100) / 100 : undefined,
        speedTier: estimateSpeed('', paramSize),
        isCoder: isCoder(name),
        isReasoning: isReasoning(name),
        isVision: isVision(name),
        capabilities: inferCapabilities(name, paramSize, ''),
      }
    })
  } finally {
    clearTimeout(timeout)
  }
}
