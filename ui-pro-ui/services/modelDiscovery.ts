// modelDiscovery.ts
// Role: Singleton service that discovers available LLM models from backends (Ollama, LMStudio, 
// llama.cpp, Lemonade), and emits events for the UI to consume
// Features: Rich metadata (size, quantization, speed tier, capabilities)

// Model Discovery Service - Discovers available models from different backends
import { events } from '@/lib/events'
import { LLM_CONFIG } from '@/lib/config'

// Speed tiers
export type SpeedTier = 'very_fast' | 'fast' | 'medium' | 'slow'

// Task capabilities
export type ModelCapability = 'code' | 'reasoning' | 'fast' | 'creative' | 'analysis' | 'vision'

interface Model {
  id: string
  name: string
  provider: 'ollama' | 'lmstudio' | 'lemonade'
  // Rich metadata
  parameterSize?: string      // ex: "8.0B", "70B"
  quantization?: string       // ex: "Q4_K_M", "FP16"
  sizeGb?: number             // Size in GB
  family?: string             // Model family
  maxContext?: number         // Estimated context window
  speedTier?: SpeedTier       // very_fast, fast, medium, slow
  isCoder?: boolean          // Code capability
  isReasoning?: boolean      // Reasoning capability
  isVision?: boolean         // Vision capability
  capabilities?: ModelCapability[]  // List of capabilities
}

interface BackendConfig {
  url: string
  enabled: boolean
}

// Use config for default backends - with NEXT_PUBLIC_ env var overrides
const defaultBackends: Record<string, BackendConfig> = {
  ollama: { url: LLM_CONFIG.ollamaUrl, enabled: true },
  lmstudio: { url: LLM_CONFIG.lmstudioUrl, enabled: true },
  llamacpp: { url: LLM_CONFIG.llamacppUrl, enabled: true },
  lemonade: { url: LLM_CONFIG.lemonadeUrl, enabled: true },
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
          maxContext: this.estimateMaxContext(paramSize || '', family || ''),
          speedTier: this.estimateSpeed(quant || '', paramSize || ''),
          isCoder: this.isCoder(m.name),
          isReasoning: this.isReasoning(m.name),
          isVision: this.isVision(m.name),
          capabilities: this.inferCapabilities(m.name, paramSize || '', family || ''),
        }
      })
    }
    // Proxy returned { model_fast: ... } - not a model list
    return []
  }

  // Helper methods for model enrichment
  private estimateMaxContext(paramSize: string, family: string): number {
    const size = paramSize.toLowerCase()
    const fam = family.toLowerCase()
    
    if (size.includes('70b') || size.includes('72b')) return 32768
    if (size.includes('32b')) return fam.includes('gemma') ? 8192 : 16384
    if (size.includes('13b') || size.includes('14b') || size.includes('8b')) return 8192
    if (size.includes('3b') || size.includes('4b') || size.includes('2b') || size.includes('1b') || size.includes('0.8b')) return 4096
    return 8192
  }

  private estimateSpeed(quantization: string, paramSize: string): SpeedTier {
    const q = quantization.toUpperCase()
    const s = paramSize.toLowerCase()
    
    if (q.includes('Q2') || q.includes('Q3') || q.includes('IQ3') || s.includes('1b') || s.includes('0.8b')) {
      return 'very_fast'
    }
    if (q.includes('Q4') || s.includes('7b') || s.includes('8b')) return 'fast'
    if (q.includes('Q5') || q.includes('Q6')) return 'medium'
    return 'slow'
  }

  private isCoder(name: string): boolean {
    const n = name.toLowerCase()
    return n.includes('coder') || n.includes('code') || (n.includes('qwen') && n.includes('2.5'))
  }

  private isReasoning(name: string): boolean {
    const n = name.toLowerCase()
    return n.includes('deepseek') || n.includes('llama') || n.includes('mistral') || n.includes('opus')
  }

  private isVision(name: string): boolean {
    const n = name.toLowerCase()
    return n.includes('vision') || n.includes('llava') || n.includes('moondream')
  }

  private inferCapabilities(name: string, paramSize: string, family: string): ModelCapability[] {
    const caps: ModelCapability[] = ['fast']
    const n = name.toLowerCase()
    
    if (this.isCoder(n)) caps.push('code')
    if (this.isReasoning(n)) caps.push('reasoning')
    if (this.isVision(n)) caps.push('vision', 'analysis')
    if (n.includes('gemma')) caps.push('creative')
    
    // Deduplicate
    return [...new Set(caps)]
  }

  private async fetchLMStudio(url: string): Promise<Model[]> {
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
      // LM Studio returns { models: [...] }
      return (data.models || []).map((m: { key: string; display_name?: string }) => ({
        id: m.key,
        name: m.display_name || m.key,
        provider: 'lmstudio' as const,
      }))
    } catch (e) {
      console.debug('[ModelDiscovery] LM Studio fetch failed:', e)
      return []
    } finally {
      clearTimeout(timeout)
    }
  }

  private async fetchLlamaCpp(url: string): Promise<Model[]> {
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
      return (data.models || []).map((m: { name: string }) => ({
        id: m.name,
        name: m.name,
        provider: 'ollama' as const,  // Treat llama.cpp as Ollama
      }))
    } catch {
      return []
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