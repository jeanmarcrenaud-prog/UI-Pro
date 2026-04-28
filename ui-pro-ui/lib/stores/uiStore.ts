// uiStore.ts
// Role: Global UI store via Zustand with persistence - manages sidebar state, compact mode toggle,
// model selection, locale settings, and available models list across the application

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { LLM_CONFIG } from '@/lib/config'

type Locale = 'en' | 'fr'

interface UIState {
  sidebarOpen: boolean
  toggleSidebar: () => void
  compactMode: boolean
  toggleCompactMode: () => void
  selectedModel: string
  setSelectedModel: (model: string) => void
  locale: Locale
  setLocale: (locale: Locale) => void
  availableModels: string[]
  setAvailableModels: (models: string[]) => void
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
      availableModels: LLM_CONFIG.defaultModels,
      setAvailableModels: (availableModels) => set({ availableModels }),
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