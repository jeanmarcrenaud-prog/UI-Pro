// infrastructure/persistence/UIStore.ts
// Role: Global UI state store via Zustand with persistence

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { LLM_CONFIG } from '@/infrastructure/config/Config'

export type Locale = 'en' | 'fr'
export type Theme = 'dark' | 'light'

export interface ModelInfo {
  id: string
  name: string
  provider: 'ollama' | 'lmstudio' | 'lemonade'
  parameterSize?: string
  quantization?: string
  sizeGb?: number
  maxContext?: number
  speedTier?: 'very_fast' | 'fast' | 'medium' | 'slow'
  isCoder?: boolean
  isReasoning?: boolean
  isVision?: boolean
  capabilities?: string[]
}

interface UIState {
  sidebarOpen: boolean
  toggleSidebar: () => void
  compactMode: boolean
  toggleCompactMode: () => void
  selectedModel: string
  setSelectedModel: (model: string) => void
  locale: Locale
  setLocale: (locale: Locale) => void
  availableModels: ModelInfo[]
  setAvailableModels: (models: ModelInfo[]) => void
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  focusMode: boolean
  toggleFocusMode: () => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      compactMode: false,
      toggleCompactMode: () => set((state) => ({ compactMode: !state.compactMode })),
      selectedModel: LLM_CONFIG.defaultModel,
      setSelectedModel: (model) => {
        console.log('[useUIStore] setSelectedModel called:', model)
        set({ selectedModel: model })
      },
      locale: 'fr',
      setLocale: (locale) => {
        console.log('[useUIStore] setLocale called:', locale)
        set({ locale })
      },
      availableModels: [],
      setAvailableModels: (availableModels) => set({ availableModels }),
      theme: 'dark',
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),
      focusMode: false,
      toggleFocusMode: () => set((state) => ({ focusMode: !state.focusMode })),
    }),
    {
      name: 'ui-pro-storage',
      partialize: (state) => ({
        selectedModel: state.selectedModel,
        sidebarOpen: state.sidebarOpen,
        compactMode: state.compactMode,
        locale: state.locale,
      }),
    }
  )
)

export const uiStore = {
  getState: () => useUIStore.getState(),
}
