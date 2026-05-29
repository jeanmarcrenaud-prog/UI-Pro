// modelDiscovery.ts
// Role: Singleton service facade that discovers LLM models from backends.
// Delegates to provider-specific implementations in ./providers/

import { events } from '@/lib/events'
import { LLM_CONFIG } from '@/lib/config'
import type { Model, SpeedTier, ModelCapability } from './providers/helpers'
import { fetchOllama } from './providers/ollama'
import { fetchLMStudio } from './providers/lmstudio'
import { fetchLlamaCpp } from './providers/llamacpp'
import { fetchLemonade } from './providers/lemonade'

// Backend configuration interface
interface BackendConfigLocal {
  url: string
  enabled: boolean
}

// Use config for default backends - with NEXT_PUBLIC_ env var overrides
const defaultBackends: Record<string, BackendConfigLocal> = {
  ollama: { url: LLM_CONFIG.ollamaUrl, enabled: true },
  lmstudio: { url: LLM_CONFIG.lmstudioUrl, enabled: true },
  llamacpp: { url: LLM_CONFIG.llamacppUrl, enabled: true },
  lemonade: { url: LLM_CONFIG.lemonadeUrl, enabled: true },
}

class ModelDiscoveryService {
  private models: Model[] = []
  private backends: Record<string, BackendConfigLocal>
  private pollInterval: number | null = null
  private isDiscovering: boolean = false

  constructor(backends: Record<string, BackendConfigLocal> = defaultBackends) {
    this.backends = backends
  }

  async discover(): Promise<Model[]> {
    // Prevent concurrent discovery
    if (this.isDiscovering) {
      console.log('[ModelDiscovery] Discovery already in progress, skipping')
      return this.models
    }

    this.isDiscovering = true

    const errors: string[] = []

    // First try to fetch from backend API (includes isLoaded/sizeVramGb)
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 5000)

      const response = await fetch('/api/models', {
        method: 'GET',
        signal: controller.signal,
      })

      clearTimeout(timeout)

      if (response.ok) {
        const data = await response.json()
        if (data.models && Array.isArray(data.models)) {
          // Transform backend model format to frontend format
          const allModels: Model[] = data.models.map((m: {
            name: string
            backend: string
            size_gb?: number
            parameter_size?: string
            quantization?: string
            speed_tier?: string
            max_context?: number
            strengths?: string[]
            is_loaded?: boolean
            size_vram_gb?: number
          }) => {
            const provider = m.backend as 'ollama' | 'lmstudio' | 'lemonade'

            return {
              id: m.name,
              name: m.name,
              provider: provider,
              sizeGb: m.size_gb,
              parameterSize: m.parameter_size,
              quantization: m.quantization,
              speedTier: m.speed_tier as SpeedTier,
              maxContext: m.max_context,
              isCoder: m.strengths?.includes('code') || false,
              isReasoning: m.strengths?.includes('reasoning') || false,
              isVision: m.strengths?.includes('vision') || false,
              capabilities: m.strengths as ModelCapability[],
              isLoaded: m.is_loaded || false,
              sizeVramGb: m.size_vram_gb,
            }
          })

          this.models = allModels
          events.emit('modelsDiscovered', { models: allModels, errors })
          this.isDiscovering = false
          return allModels
        }
      }
    } catch (e) {
      console.debug('[ModelDiscovery] Backend API unavailable, using direct discovery:', e)
      errors.push(`backend_api: ${(e as Error)?.message || String(e)}`)
    }

    // Fallback to direct backend discovery
    const allModels: Model[] = []
    const entries = Object.entries(this.backends).filter(([_, config]) => config.enabled)
    const promises = entries.map(([provider, config]) =>
      this.fetchFromBackend(provider, config.url).catch(e => {
        errors.push(`${provider}: ${e?.message || e}`)
        return []
      })
    )

    const results = await Promise.allSettled(promises)

    results.forEach((result) => {
      if (result.status === 'fulfilled' && result.value.length > 0) {
        allModels.push(...result.value)
      }
    })

    this.models = allModels

    // Emit event - let caller update UI store
    events.emit('modelsDiscovered', { models: allModels, errors })

    this.isDiscovering = false
    return allModels
  }

  private async fetchFromBackend(
    provider: string,
    url: string
  ): Promise<Model[]> {
    try {
      switch (provider) {
        case 'ollama':
          return await fetchOllama(url)
        case 'lmstudio':
          return await fetchLMStudio(url)
        case 'llamacpp':
          return await fetchLlamaCpp(url)
        case 'lemonade':
          return await fetchLemonade(url)
        default:
          return []
      }
    } catch (e) {
      console.debug(`[ModelDiscovery] Backend ${provider} unavailable:`, e)
      return []
    }
  }

  // Start polling for model updates
  startPolling(intervalMs: number = 60000): void {
    this.stopPolling()
    this.pollInterval = window.setInterval(() => {
      if (!this.isDiscovering) {
        this.discover()
      }
    }, intervalMs)
  }

  stopPolling(): void {
    if (this.pollInterval) {
      clearInterval(this.pollInterval)
      this.pollInterval = null
    }
  }

  getModels(): Model[] {
    return [...this.models]
  }

  getModelsByProvider(provider: string): Model[] {
    return this.models.filter(m => m.provider === provider)
  }
}

export const modelDiscovery = new ModelDiscoveryService()
export type { Model, BackendConfigLocal as BackendConfig }
