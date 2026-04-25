// config.ts
// Role: Centralized configuration - single source of truth for frontend
// All config should come from environment variables (NEXT_PUBLIC_ for client-accessible)
// Used by: services, components - import from here instead of hardcoding

// API Configuration
export const API_CONFIG = {
  // FastAPI backend
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  wsUrl: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  
  // Timeouts
  connectTimeout: 8000,
  requestTimeout: 60000,
}

// LLM Backend Configuration
export const LLM_CONFIG = {
  // Ollama (default)
  ollamaUrl: process.env.NEXT_PUBLIC_OLLAMA_URL || 'http://localhost:11434',
  
  // LM Studio
  lmstudioUrl: process.env.NEXT_PUBLIC_LMSTUDIO_URL || 'http://localhost:1234',
  
  // llama.cpp
  llamacppUrl: process.env.NEXT_PUBLIC_LLAMACPP_URL || 'http://localhost:8080',
  
  // Lemonade
  lemonadeUrl: process.env.NEXT_PUBLIC_LEMONADE_URL || 'http://localhost:13305',
  
  // Default model - should be overridden via API at runtime
  defaultModel: process.env.NEXT_PUBLIC_DEFAULT_MODEL || 'qwen3.5:9b',
  
  // Default available models (fallback list)
  defaultModels: [
    'qwen3.5:0.8b',
    'qwen3.5:9b',
    'gemma4:latest',
    'gemma4:e4b',
    'lfm2:latest',
    'nemotron-cascade-2:latest',
  ],
}

// Export combined config object for convenience
export const config = {
  ...API_CONFIG,
  ...LLM_CONFIG,
}

// Type exports for consumers
export type API_CONFIG_TYPE = typeof API_CONFIG
export type LLM_CONFIG_TYPE = typeof LLM_CONFIG