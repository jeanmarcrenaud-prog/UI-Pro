// infrastructure/config/Config.ts
// Role: Centralized configuration - single source of truth for frontend
import type { API_CONFIG_TYPE, LLM_CONFIG_TYPE } from './Config'

export const API_CONFIG = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  connectTimeout: 8000,
  requestTimeout: 60000,
} as const

export const LLM_CONFIG = {
  ollamaUrl: process.env.NEXT_PUBLIC_OLLAMA_URL || 'http://localhost:11434',
  lmstudioUrl: process.env.NEXT_PUBLIC_LMSTUDIO_URL || 'http://localhost:1234',
  llamacppUrl: process.env.NEXT_PUBLIC_LLAMACPP_URL || 'http://localhost:8080',
  lemonadeUrl: process.env.NEXT_PUBLIC_LEMONADE_URL || 'http://localhost:13305',
  defaultModel: process.env.NEXT_PUBLIC_DEFAULT_MODEL || 'qwen3.6:latest',
  defaultModels: [] as string[],
} as const

export const config = {
  ...API_CONFIG,
  ...LLM_CONFIG,
}

export type { API_CONFIG_TYPE, LLM_CONFIG_TYPE }
export type { API_CONFIG as ApiConfig } from './Config'
export type { LLM_CONFIG as LlmConfig } from './Config'
