// components/settings/types.ts
// Shared types for Settings components

export interface BackendInfo {
  name: string
  url: string
  status: 'active' | 'inactive' | 'error'
  responseTime?: number
  modelCount?: number
  lastChecked?: number
}

export interface SettingsMessage {
  type: 'success' | 'error'
  text: string
}

export interface TimeoutValues {
  llmTimeout: number
  executorTimeout: number
}

export interface LogLevelState {
  currentLevel: string
  availableLevels: string[]
  isSaving: boolean
  message: SettingsMessage | null
}

export interface ModelSearchState {
  search: string
  isRefreshing: boolean
  error: string | null
}