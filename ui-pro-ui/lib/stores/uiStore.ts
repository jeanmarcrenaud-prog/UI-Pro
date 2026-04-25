// uiStore.ts
// Role: Global UI store via Zustand with persistence - manages sidebar state, compact mode toggle,
// model selection, and available models list across the application

// UI Store - Unified UI state management with persistence
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { LLM_CONFIG } from '@/lib/config'

interface UIState {
  // Sidebar
  sidebarOpen: boolean
  toggleSidebar: () => void
  
  // Compact mode (dense message history)
  compactMode: boolean
  toggleCompactMode: () => void
  
  // Model
  selectedModel: string
  setSelectedModel: (model: string) => void
  
  // Available models
  availableModels: string[]
  setAvailableModels: (models: string[]) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      // Sidebar
      sidebarOpen: true,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      
      // Compact mode
      compactMode: false,
      toggleCompactMode: () => set((state) => ({ compactMode: !state.compactMode })),
      
      // Model - initialized from config, should be overridden from API on mount
      selectedModel: LLM_CONFIG.defaultModel,
      setSelectedModel: (model) => {
        console.log('[useUIStore] setSelectedModel called:', model)
        set({ selectedModel: model })
      },
      
      // Available models - initialized from config (will be refreshed from API)
      availableModels: LLM_CONFIG.defaultModels,
      setAvailableModels: (availableModels) => set({ availableModels }),
    }),
    {
      name: 'ui-pro-storage', // localStorage key
      partialize: (state) => ({ 
        selectedModel: state.selectedModel,
        sidebarOpen: state.sidebarOpen,
        compactMode: state.compactMode,
      }), // Only persist these
    }
  )
)