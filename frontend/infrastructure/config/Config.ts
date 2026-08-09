// infrastructure/config/Config.ts
// Role: Re-exports from canonical config — single source of truth is lib/config.ts
// This file exists for backwards compatibility with imports from '@/infrastructure/config'.

export {
  API_CONFIG,
  LLM_CONFIG,
  config,
  type API_CONFIG_TYPE,
  type LLM_CONFIG_TYPE,
} from '@/lib/config'
