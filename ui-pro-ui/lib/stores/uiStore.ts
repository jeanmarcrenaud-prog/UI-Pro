// UI Store - Unified UI state management
import { create } from 'zustand'

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
  
  // Model
  selectedModel: string
  setSelectedModel: (model: string) => void
  
  // Available models
  availableModels: string[]
  setAvailableModels: (models: string[]) => void
}

export const useUIStore = create<UIState>((set) => ({
  // Connection
  connectionStatus: 'disconnected',
  setConnectionStatus: (connectionStatus) => set({ connectionStatus }),
  
  // Sidebar
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  
  // Debug panel
  debugPanelOpen: true,
  toggleDebugPanel: () => set((state) => ({ debugPanelOpen: !state.debugPanelOpen })),
  
  // Model
  selectedModel: 'gemma4',
  setSelectedModel: (selectedModel) => set({ selectedModel }),
  
  // Available models
  availableModels: ['gemma4', 'qwen-coder', 'mistral', 'deepseek'],
  setAvailableModels: (availableModels) => set({ availableModels }),
}))