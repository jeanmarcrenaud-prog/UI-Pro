// UI Store - Unified UI state management with persistence
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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
      
      // Model - initialized empty, will be set from API on mount
      selectedModel: 'qwen3.5:9b',  // Default to 9b, not empty
      setSelectedModel: (model) => {
        console.log('[useUIStore] setSelectedModel called:', model)
        set({ selectedModel: model })
      },
      
      // Available models - defaults (will be refreshed from API)
      availableModels: [
        'qwen3.5:0.8b',
        'gemma4:latest',
        'gemma4:e4b', 
        'lfm2:latest',
        'nemotron-cascade-2:latest',
        'qwen3.5:9b'
      ],
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