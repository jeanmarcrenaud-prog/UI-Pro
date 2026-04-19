// Model Discovery Service - Discovers available models from different backends
import { useUIStore } from '@/lib/stores/uiStore'
import { events } from '@/lib/events'

interface Model {
  id: string
  name: string
  provider: 'ollama' | 'lmstudio' | 'llama.cpp' | 'lemonade'
}

interface BackendConfig {
  url: string
  enabled: boolean
}

const defaultBackends: Record<string, BackendConfig> = {
  ollama: { url: 'http://localhost:11434', enabled: true },
  lmstudio: { url: 'http://localhost:1234', enabled: true },
  llamacpp: { url: 'http://localhost:8080', enabled: true },
  lemonade: { url: 'http://localhost:13305', enabled: true },
}

class ModelDiscoveryService {
  private models: Model[] = []
  private backends: Record<string, BackendConfig>
  private pollInterval: number | null = null

  constructor(backends: Record<string, BackendConfig> = defaultBackends) {
    this.backends = backends
  }

  async discover(): Promise<Model[]> {
    const allModels: Model[] = []
    const errors: string[] = []

    // Discover from each enabled backend in parallel
    const entries = Object.entries(this.backends).filter(([_, config]) => config.enabled)
    const promises = entries.map(([provider, config]) => 
      this.fetchFromBackend(provider, config.url).catch(e => {
        errors.push(`${provider}: ${e?.message || e}`)
        return []
      })
    )

    const results = await Promise.allSettled(promises)
    
    results.forEach((result, index) => {
      if (result.status === 'fulfilled' && result.value.length > 0) {
        allModels.push(...result.value)
      }
    })

    this.models = allModels
    
    // Update UI store - use store defaults if no models found
    const modelIds = allModels.length > 0 
      ? allModels.map(m => m.id)
      : useUIStore.getState().availableModels // Keep defaults
    
    useUIStore.getState().setAvailableModels(modelIds)
    
    // Fetch default model from backend settings and use as initial selection
    try {
      const response = await fetch('/api/settings/default-model', {
        signal: AbortSignal.timeout(5000),
      })
      if (response.ok) {
        const data = await response.json()
        const defaultModel = data.model_fast
        // Only set if no model is currently selected
        if (!useUIStore.getState().selectedModel && defaultModel) {
          useUIStore.getState().setSelectedModel(defaultModel)
        }
      }
    } catch {
      // Fallback: use first available model
      if (modelIds.length > 0 && !useUIStore.getState().selectedModel) {
        useUIStore.getState().setSelectedModel(modelIds[0])
      }
    }
    
    // Emit event
    events.emit('modelsDiscovered', { models: allModels, errors })
    
    return allModels
  }

  private async fetchFromBackend(
    provider: string,
    url: string
  ): Promise<Model[]> {
    try {
      switch (provider) {
        case 'ollama':
          return await this.fetchOllama(url)
        case 'lmstudio':
          return await this.fetchLMStudio(url)
        case 'llamacpp':
          return await this.fetchLlamaCpp(url)
        case 'lemonade':
          return await this.fetchLemonade(url)
        default:
          return []
      }
    } catch {
      // Silently fail - backend not available
      return []
    }
  }

  private async fetchOllama(url: string): Promise<Model[]> {
    let response: Response
    
    try {
      // Try direct first
      response = await fetch(`${url}/api/tags`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
      })
    } catch {
      // Fallback to proxy if direct fails (CORS)
      try {
        response = await fetch('/api/models', {
          method: 'GET',
          signal: AbortSignal.timeout(3000),
        })
      } catch {
        return [] // Silently fail
      }
    }
    
    if (!response.ok) return []
    
    const data = await response.json()
    const models = data.models || []
    return models.map((m: { name: string }) => ({
      id: m.name,
      name: m.name,
      provider: 'ollama' as const,
    }))
  }

  private async fetchLMStudio(url: string): Promise<Model[]> {
    const response = await fetch(`${url}/api/models`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    })
    
    if (!response.ok) return []
    
    const data = await response.json()
    return (data.data || []).map((m: { id: string; name: string }) => ({
      id: m.id,
      name: m.name,
      provider: 'lmstudio' as const,
    }))
  }

  private async fetchLlamaCpp(url: string): Promise<Model[]> {
    // llama.cpp usually uses specific endpoint
    const response = await fetch(`${url}/v1/models`, {
      method: 'GET',
      headers: { 'Authorization': 'Bearer empty' },
      signal: AbortSignal.timeout(5000),
    })
    
    if (!response.ok) return []
    
    const data = await response.json()
    return (data.data || []).map((m: { id: string }) => ({
      id: m.id,
      name: m.id,
      provider: 'llama.cpp' as const,
    }))
  }

  private async fetchLemonade(url: string): Promise<Model[]> {
    const response = await fetch(`${url}/api/v1/models`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    })
    
    if (!response.ok) return []
    
    const data = await response.json()
    return (data.data || []).map((m: { id: string; labels?: string[] }) => ({
      id: m.id,
      name: m.id,
      provider: 'lemonade' as const,
    }))
  }

  // Start polling for model updates
  startPolling(intervalMs: number = 60000): void {
    this.stopPolling()
    this.pollInterval = window.setInterval(() => {
      this.discover()
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
export type { Model, BackendConfig }