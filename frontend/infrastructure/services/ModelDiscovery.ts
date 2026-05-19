// infrastructure/services/ModelDiscovery.ts
// Role: Discovers available LLM models from backends (Ollama, LMStudio, llama.cpp, Lemonade)

import { events } from '@/infrastructure/events/EventBus';
import { LLM_CONFIG } from '@/infrastructure/config/Config';

export type SpeedTier = 'very_fast' | 'fast' | 'medium' | 'slow';

export type ModelCapability = 'code' | 'reasoning' | 'fast' | 'creative' | 'analysis' | 'vision';

interface Model {
  id: string;
  name: string;
  provider: 'ollama' | 'lmstudio' | 'lemonade';
  parameterSize?: string;
  quantization?: string;
  sizeGb?: number;
  family?: string;
  maxContext?: number;
  speedTier?: SpeedTier;
  isCoder?: boolean;
  isReasoning?: boolean;
  isVision?: boolean;
  capabilities?: ModelCapability[];
}

interface BackendConfig {
  url: string;
  enabled: boolean;
}

const defaultBackends: Record<string, BackendConfig> = {
  ollama: { url: LLM_CONFIG.ollamaUrl, enabled: true },
  lmstudio: { url: LLM_CONFIG.lmstudioUrl, enabled: true },
  llamacpp: { url: LLM_CONFIG.llamacppUrl, enabled: true },
  lemonade: { url: LLM_CONFIG.lemonadeUrl, enabled: true },
};

class ModelDiscoveryService {
  private models: Model[] = [];
  private backends: Record<string, BackendConfig>;
  private pollInterval: number | null = null;
  private isDiscovering: boolean = false;

  constructor(backends: Record<string, BackendConfig> = defaultBackends) {
    this.backends = backends;
  }

  async discover(): Promise<Model[]> {
    if (this.isDiscovering) {
      console.log('[ModelDiscovery] Discovery already in progress, skipping');
      return this.models;
    }

    this.isDiscovering = true;
    const allModels: Model[] = [];
    const errors: string[] = [];

    const entries = Object.entries(this.backends).filter(([_, config]) => config.enabled);
    const promises = entries.map(([provider, config]) =>
      this.fetchFromBackend(provider, config.url).catch((e) => {
        errors.push(`${provider}: ${e?.message || e}`);
        return [];
      })
    );

    const results = await Promise.allSettled(promises);

    results.forEach((result, index) => {
      if (result.status === 'fulfilled' && result.value.length > 0) {
        allModels.push(...result.value);
      }
    });

    this.models = allModels;
    events.emit('modelsDiscovered', { models: allModels, errors });
    this.isDiscovering = false;
    return allModels;
  }

  private async fetchFromBackend(provider: string, url: string): Promise<Model[]> {
    try {
      switch (provider) {
        case 'ollama':
          return await this.fetchOllama(url);
        case 'lmstudio':
          return await this.fetchLMStudio(url);
        case 'llamacpp':
          return await this.fetchLlamaCpp(url);
        case 'lemonade':
          return await this.fetchLemonade(url);
        default:
          return [];
      }
    } catch (e) {
      console.debug(`[ModelDiscovery] Backend ${provider} unavailable:`, e);
      return [];
    }
  }

  private async fetchOllama(url: string): Promise<Model[]> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);

    let response: Response;
    try {
      response = await fetch(`${url}/api/tags`, {
        method: 'GET',
        signal: controller.signal,
      });
    } catch {
      try {
        const proxyController = new AbortController();
        const proxyTimeout = setTimeout(() => proxyController.abort(), 3000);
        response = await fetch('/api/settings/default-model', {
          method: 'GET',
          signal: proxyController.signal,
        });
        clearTimeout(proxyTimeout);
      } catch {
        return [];
      }
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) return [];

    const data = await response.json();
    if (data.models) {
      return data.models.map(
        (m: {
          name: string;
          size?: number;
          details?: Record<string, unknown>;
        }) => {
          const details = m.details || {};
          const paramSize = details.parameter_size as string | undefined;
          const quant = details.quantization_level as string | undefined;
          const family = details.family as string | undefined;
          const sizeBytes = m.size || 0;

          return {
            id: m.name,
            name: m.name,
            provider: 'ollama' as const,
            parameterSize: paramSize,
            quantization: quant,
            sizeGb:
              sizeBytes > 0
                ? Math.round((sizeBytes / 1024 / 1024 / 1024) * 100) / 100
                : undefined,
            family,
            maxContext: this.estimateMaxContext(paramSize || '', family || ''),
            speedTier: this.estimateSpeed(quant || '', paramSize || ''),
            isCoder: this.isCoder(m.name),
            isReasoning: this.isReasoning(m.name),
            isVision: this.isVision(m.name),
            capabilities: this.inferCapabilities(m.name, paramSize || '', family || ''),
          };
        }
      );
    }
    return [];
  }

  private estimateMaxContext(paramSize: string, family: string): number {
    const size = paramSize.toLowerCase();
    const fam = family.toLowerCase();

    if (size.includes('70b') || size.includes('72b')) return 32768;
    if (size.includes('32b')) return fam.includes('gemma') ? 8192 : 16384;
    if (size.includes('13b') || size.includes('14b') || size.includes('8b')) return 8192;
    if (size.includes('3b') || size.includes('4b') || size.includes('2b') || size.includes('1b') || size.includes('0.8b')) return 4096;
    return 8192;
  }

  private estimateSpeed(quantization: string, paramSize: string): SpeedTier {
    const q = quantization.toUpperCase();
    const s = paramSize.toLowerCase();

    if (q.includes('Q2') || q.includes('Q3') || q.includes('IQ3') || s.includes('1b') || s.includes('0.8b')) {
      return 'very_fast';
    }
    if (q.includes('Q4') || s.includes('7b') || s.includes('8b')) return 'fast';
    if (q.includes('Q5') || q.includes('Q6')) return 'medium';
    return 'slow';
  }

  private isCoder(name: string): boolean {
    const n = name.toLowerCase();
    return n.includes('coder') || n.includes('code') || (n.includes('qwen') && n.includes('2.5'));
  }

  private isReasoning(name: string): boolean {
    const n = name.toLowerCase();
    return n.includes('deepseek') || n.includes('llama') || n.includes('mistral') || n.includes('opus');
  }

  private isVision(name: string): boolean {
    const n = name.toLowerCase();
    return n.includes('vision') || n.includes('llava') || n.includes('moondream');
  }

  private inferCapabilities(name: string, paramSize: string, family: string): ModelCapability[] {
    const caps: ModelCapability[] = ['fast'];
    const n = name.toLowerCase();

    if (this.isCoder(n)) caps.push('code');
    if (this.isReasoning(n)) caps.push('reasoning');
    if (this.isVision(n)) caps.push('vision', 'analysis');
    if (n.includes('gemma')) caps.push('creative');

    return [...new Set(caps)];
  }

  private async fetchLMStudio(url: string): Promise<Model[]> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    try {
      const response = await fetch(`${url}/api/v1/models`, {
        method: 'GET',
        signal: controller.signal,
      });

      if (!response.ok) return [];

      const data = await response.json();
      return (data.models || []).map(
        (m: {
          key: string;
          display_name?: string;
          architecture?: string;
          quantization?: { name?: string; bits_per_weight?: number };
          size_bytes?: number;
          params_string?: string;
          max_context_length?: number;
        }) => {
          const quant = m.quantization?.name;
          const paramSize = m.params_string || '';
          const sizeBytes = m.size_bytes || 0;

          return {
            id: m.key,
            name: m.display_name || m.key,
            provider: 'lmstudio' as const,
            parameterSize: paramSize || undefined,
            quantization: quant,
            sizeGb:
              sizeBytes > 0
                ? Math.round((sizeBytes / 1024 / 1024 / 1024) * 100) / 100
                : undefined,
            family: m.architecture,
            maxContext: m.max_context_length,
            speedTier: this.estimateSpeed(quant || '', paramSize),
            isCoder: this.isCoder(m.display_name || m.key),
            isReasoning: this.isReasoning(m.display_name || m.key),
            isVision: this.isVision(m.display_name || m.key),
            capabilities: this.inferCapabilities(
              m.display_name || m.key,
              paramSize,
              m.architecture || ''
            ),
          };
        }
      );
    } catch (e) {
      console.debug('[ModelDiscovery] LM Studio fetch failed:', e);
      return [];
    } finally {
      clearTimeout(timeout);
    }
  }

  private async fetchLlamaCpp(url: string): Promise<Model[]> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    try {
      const response = await fetch(`${url}/api/tags`, {
        method: 'GET',
        signal: controller.signal,
      });

      if (!response.ok) return [];

      const data = await response.json();
      return (data.models || []).map(
        (m: {
          name: string;
          size?: number;
          details?: Record<string, unknown>;
        }) => {
          const details = m.details || {};
          const paramSize = details.parameter_size as string | undefined;
          const quant = details.quantization_level as string | undefined;
          const family = details.family as string | undefined;
          const sizeBytes = m.size || 0;

          return {
            id: m.name,
            name: m.name,
            provider: 'ollama' as const,
            parameterSize: paramSize,
            quantization: quant,
            sizeGb:
              sizeBytes > 0
                ? Math.round((sizeBytes / 1024 / 1024 / 1024) * 100) / 100
                : undefined,
            family,
            maxContext: this.estimateMaxContext(paramSize || '', family || ''),
            speedTier: this.estimateSpeed(quant || '', paramSize || ''),
            isCoder: this.isCoder(m.name),
            isReasoning: this.isReasoning(m.name),
            isVision: this.isVision(m.name),
            capabilities: this.inferCapabilities(m.name, paramSize || '', family || ''),
          };
        }
      );
    } catch {
      return [];
    } finally {
      clearTimeout(timeout);
    }
  }

  private async fetchLemonade(url: string): Promise<Model[]> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    try {
      const response = await fetch(`${url}/api/v1/models`, {
        method: 'GET',
        signal: controller.signal,
      });

      if (!response.ok) return [];

      const data = await response.json();
      return (data.data || []).map(
        (m: {
          id: string;
          labels?: string[];
          size?: number;
        }) => {
          const name = m.id;
          const nameLower = name.toLowerCase();
          let paramSize = '';
          if (m.labels) {
            const sizeLabel = m.labels.find((l) => l.match(/\d+b/i));
            if (sizeLabel) paramSize = sizeLabel;
          }

          return {
            id: m.id,
            name: m.id,
            provider: 'lemonade' as const,
            parameterSize: paramSize || undefined,
            sizeGb: m.size ? Math.round(m.size / 1024 / 1024 / 1024 * 100) / 100 : undefined,
            speedTier: this.estimateSpeed('', paramSize),
            isCoder: this.isCoder(name),
            isReasoning: this.isReasoning(name),
            isVision: this.isVision(name),
            capabilities: this.inferCapabilities(name, paramSize, ''),
          };
        }
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  startPolling(intervalMs: number = 60000): void {
    this.stopPolling();
    this.pollInterval = window.setInterval(() => {
      if (!this.isDiscovering) {
        this.discover();
      }
    }, intervalMs);
  }

  stopPolling(): void {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  getModels(): Model[] {
    return [...this.models];
  }

  getModelsByProvider(provider: string): Model[] {
    return this.models.filter((m) => m.provider === provider);
  }
}

export const modelDiscovery = new ModelDiscoveryService();
export type { Model, BackendConfig };
