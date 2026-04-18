// UI Store - Unified UI state management with persistence
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

interface UIState {
  // Connection
  connectionStatus: ConnectionStatus
  setConnectionStatus: (status: ConnectionStatus) => void
  
  // Sidebar
  sidebarOpen: boolean
  toggleSidebar: () => void
  
  // Debug panel
  debugPanelOpen: boolean
  toggleDebugPanel: () => void
  
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
      // Connection
      connectionStatus: 'disconnected',
      setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
      
      // Sidebar
      sidebarOpen: true,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      
      // Debug panel
      debugPanelOpen: true,
      toggleDebugPanel: () => set((state) => ({ debugPanelOpen: !state.debugPanelOpen })),
      
      // Compact mode
      compactMode: false,
      toggleCompactMode: () => set((state) => ({ compactMode: !state.compactMode })),
      
// Model - initialized empty, will be set from API on mount
  selectedModel: '',
  setSelectedModel: (selectedModel) => set({ selectedModel }),
  
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
        debugPanelOpen: state.debugPanelOpen,
        compactMode: state.compactMode,
      }), // Only persist these
    }
  )
)