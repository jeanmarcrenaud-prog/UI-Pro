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
  llamacpp: { url: 'http://localhost:8080', enabled: false },
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

    // Discover from each backend in parallel
    const promises = Object.entries(this.backends)
      .filter(([_, config]) => config.enabled)
      .map(([provider, config]) => this.fetchFromBackend(provider, config.url))

    const results = await Promise.allSettled(promises)
    
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        allModels.push(...result.value)
      }
    })

    this.models = allModels
    
    // Update UI store
    const modelIds = allModels.map(m => m.id)
    useUIStore.getState().setAvailableModels(modelIds)
    useUIStore.getState().setSelectedModel(modelIds[0] || 'gemma4')
    
    // Emit event
    events.emit('modelsDiscovered', { models: allModels })
    
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
      console.warn(`Failed to fetch models from ${provider}: ${url}`)
      return []
    }
  }

  private async fetchOllama(url: string): Promise<Model[]> {
    const response = await fetch(`${url}/api/tags`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    })
    
    if (!response.ok) return []
    
    const data = await response.json()
    return (data.models || []).map((m: { name: string }) => ({
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
    return (data.models || []).map((m: { name: string }) => ({
      id: m.name,
      name: m.name,
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