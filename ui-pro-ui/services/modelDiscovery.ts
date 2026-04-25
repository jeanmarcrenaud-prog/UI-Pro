// modelDiscovery.ts
// Role: Singleton service that discovers available LLM models from backends (Ollama, LMStudio, 
// llama.cpp, Lemonade), updates the UI store, fetches default model from settings, and polls for updates

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
  private isDiscovering: boolean = false

  constructor(backends: Record<string, BackendConfig> = defaultBackends) {
    this.backends = backends
  }

  async discover(): Promise<Model[]> {
    // Prevent concurrent discovery
    if (this.isDiscovering) {
      console.log('[ModelDiscovery] Discovery already in progress, skipping')
      return this.models
    }

    this.isDiscovering = true
    
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
    // ONLY if no model is already selected (preserve user choice!)
    try {
      const settingsController = new AbortController()
      const settingsTimeout = setTimeout(() => settingsController.abort(), 5000)
      const response = await fetch('/api/settings/default-model', {
        signal: settingsController.signal,
      })
      clearTimeout(settingsTimeout)

      if (response.ok) {
        const data = await response.json()
        const defaultModel = data?.model_fast
        // Only set if no model (strict null check, allow empty string)
        const current = useUIStore.getState().selectedModel
        if (!current && current !== '' && defaultModel) {
          useUIStore.getState().setSelectedModel(defaultModel)
        }
      }
    } catch {
      // Fallback: use first available model, but ONLY if nothing selected
      const current = useUIStore.getState().selectedModel
      if (modelIds.length > 0 && (!current || current === '')) {
        useUIStore.getState().setSelectedModel(modelIds[0])
      }
    }
    
    // Emit event
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
    } catch (e) {
      console.debug(`[ModelDiscovery] Backend ${provider} unavailable:`, e)
      return []
    }
  }

  private async fetchOllama(url: string): Promise<Model[]> {
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
      return data.models.map((m: { name: string }) => ({
        id: m.name,
        name: m.name,
        provider: 'ollama' as const,
      }))
    }
    // Proxy returned { model_fast: ... } - not a model list
    return []
  }

  private async fetchLMStudio(url: string): Promise<Model[]> {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    
    try {
      const response = await fetch(`${url}/api/models`, {
        method: 'GET',
        signal: controller.signal,
      })
      
      if (!response.ok) return []
      
      const data = await response.json()
      return (data.data || []).map((m: { id: string; name: string }) => ({
        id: m.id,
        name: m.name,
        provider: 'lmstudio' as const,
      }))
    } finally {
      clearTimeout(timeout)
    }
  }

  private async fetchLlamaCpp(url: string): Promise<Model[]> {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    
    try {
      const response = await fetch(`${url}/v1/models`, {
        method: 'GET',
        headers: { 'Authorization': 'Bearer empty' },
        signal: controller.signal,
      })
      
      if (!response.ok) return []
      
      const data = await response.json()
      return (data.data || []).map((m: { id: string }) => ({
        id: m.id,
        name: m.id,
        provider: 'llama.cpp' as const,
      }))
    } finally {
      clearTimeout(timeout)
    }
  }

  private async fetchLemonade(url: string): Promise<Model[]> {
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
      return (data.data || []).map((m: { id: string; labels?: string[] }) => ({
        id: m.id,
        name: m.id,
        provider: 'lemonade' as const,
      }))
    } finally {
      clearTimeout(timeout)
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
export type { Model, BackendConfig }