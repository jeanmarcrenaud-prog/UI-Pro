// providers/helpers.ts
// Role: Shared types and helper functions for model discovery providers

// Speed tiers
export type SpeedTier = 'very_fast' | 'fast' | 'medium' | 'slow'

// Task capabilities
export type ModelCapability = 'code' | 'reasoning' | 'fast' | 'creative' | 'analysis' | 'vision'

export interface Model {
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
  isReasoning?: boolean       // Reasoning capability
  isVision?: boolean          // Vision capability
  capabilities?: ModelCapability[]  // List of capabilities
  // VRAM status
  isLoaded?: boolean          // Whether model is loaded in VRAM
  sizeVramGb?: number         // VRAM used if loaded
}

// Helper methods for model enrichment
export function estimateMaxContext(paramSize: string, family: string): number {
  const size = paramSize.toLowerCase()
  const fam = family.toLowerCase()

  if (size.includes('70b') || size.includes('72b')) return 32768
  if (size.includes('32b')) return fam.includes('gemma') ? 8192 : 16384
  if (size.includes('13b') || size.includes('14b') || size.includes('8b')) return 8192
  if (size.includes('3b') || size.includes('4b') || size.includes('2b') || size.includes('1b') || size.includes('0.8b')) return 4096
  return 8192
}

export function estimateSpeed(quantization: string, paramSize: string): SpeedTier {
  const q = quantization.toUpperCase()
  const s = paramSize.toLowerCase()

  if (q.includes('Q2') || q.includes('Q3') || q.includes('IQ3') || s.includes('1b') || s.includes('0.8b')) {
    return 'very_fast'
  }
  if (q.includes('Q4') || s.includes('7b') || s.includes('8b')) return 'fast'
  if (q.includes('Q5') || q.includes('Q6')) return 'medium'
  return 'slow'
}

export function isCoder(name: string): boolean {
  const n = name.toLowerCase()
  return n.includes('coder') || n.includes('code') || (n.includes('qwen') && n.includes('2.5'))
}

export function isReasoning(name: string): boolean {
  const n = name.toLowerCase()
  return n.includes('deepseek') || n.includes('llama') || n.includes('mistral') || n.includes('opus')
}

export function isVision(name: string): boolean {
  const n = name.toLowerCase()
  return n.includes('vision') || n.includes('llava') || n.includes('moondream')
}

export function inferCapabilities(name: string, paramSize: string, family: string): ModelCapability[] {
  const caps: ModelCapability[] = ['fast']
  const n = name.toLowerCase()

  if (isCoder(n)) caps.push('code')
  if (isReasoning(n)) caps.push('reasoning')
  if (isVision(n)) caps.push('vision', 'analysis')
  if (n.includes('gemma')) caps.push('creative')

  // Deduplicate
  return [...new Set(caps)]
}
