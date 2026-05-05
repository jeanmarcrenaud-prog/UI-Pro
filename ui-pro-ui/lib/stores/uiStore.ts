// uiStore.ts
// Role: Global UI store via Zustand with persistence - manages sidebar state, compact mode toggle,
// model selection, locale settings, and available models list across the application

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { LLM_CONFIG } from '@/lib/config'

type Locale = 'en' | 'fr'
type Theme = 'dark' | 'light'

// Model with provider and rich metadata info
export interface ModelInfo {
  id: string           // Backend key (e.g., "qwen/qwen3.5-9b" for LM Studio)
  name: string         // Display name (e.g., "Qwen3.5 9B")
  provider: 'ollama' | 'lmstudio' | 'lemonade'
  // Rich metadata
  parameterSize?: string      // ex: "8.0B", "70B"
  quantization?: string       // ex: "Q4_K_M", "FP16"
  sizeGb?: number            // Size in GB
  maxContext?: number        // Estimated context window
  speedTier?: 'very_fast' | 'fast' | 'medium' | 'slow'
  isCoder?: boolean
  isReasoning?: boolean
  isVision?: boolean
  capabilities?: string[]     // List of capabilities
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
  // Theme
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  // Focus mode
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
      availableModels: [],  // Dynamically discovered, no defaults
      setAvailableModels: (availableModels) => set({ availableModels }),
      // Theme
      theme: 'dark',
      setTheme: (theme) => set({ theme }),
      toggleTheme: () => set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),
      // Focus mode
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