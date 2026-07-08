import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export interface DebugLog {
  id: string
  timestamp: number
  type: 'step' | 'token' | 'tool' | 'error' | 'info'
  step?: string
  content: string
  duration?: number
  tokens?: number
}

export interface AgentStep {
  id: string
  name: string
  status: 'pending' | 'active' | 'completed' | 'error'
  description?: string
  duration?: number
  progress?: number // 0-100
}

interface UIState {
  // Debug Panel
  debugLogs: DebugLog[]
  isDebugEnabled: boolean
  currentAgentSteps: AgentStep[]

  // UI Generale
  sidebarOpen: boolean
  activeTab: 'chat' | 'history' | 'settings' | 'canvas'
  compactMode: boolean

  // Model
  selectedModel: string
  setSelectedModel: (model: string) => void
  availableModels: {
    id: string
    name: string
    provider: string
    isLoaded?: boolean
    sizeVramGb?: number
    sizeGb?: number
    parameterSize?: string
    quantization?: string
    speedTier?: 'very_fast' | 'fast' | 'medium' | 'slow'
    maxContext?: number
    capabilities?: string[]
    isCoder?: boolean
    isReasoning?: boolean
    isVision?: boolean
  }[]
  setAvailableModels: (models: {
    id: string
    name: string
    provider: string
    isLoaded?: boolean
    sizeVramGb?: number
    sizeGb?: number
    parameterSize?: string
    quantization?: string
    speedTier?: 'very_fast' | 'fast' | 'medium' | 'slow'
    maxContext?: number
    capabilities?: string[]
    isCoder?: boolean
    isReasoning?: boolean
    isVision?: boolean
  }[]) => void

  // Locale
  locale: 'en' | 'fr'
  setLocale: (locale: 'en' | 'fr') => void

  // Theme
  theme: 'dark' | 'light' | 'purple-rain' | 'pro'
  setTheme: (theme: 'dark' | 'light' | 'purple-rain' | 'pro') => void
  setTheme: (theme: 'dark' | 'light' | 'purple-rain') => void
  toggleTheme: () => void

  // Focus mode
  focusMode: boolean
  toggleFocusMode: () => void

  // Actions Debug
  addDebugLog: (log: Omit<DebugLog, 'id' | 'timestamp'>) => void
  clearDebugLogs: () => void
  setDebugEnabled: (enabled: boolean) => void

  // Actions Agent Steps
  setAgentSteps: (steps: AgentStep[]) => void
  updateStep: (stepId: string, updates: Partial<AgentStep>) => void
  clearAgentSteps: () => void

  // UI Actions
  toggleSidebar: () => void
  setActiveTab: (tab: 'chat' | 'history' | 'settings' | 'canvas') => void
  toggleCompactMode: () => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      debugLogs: [],
      isDebugEnabled: true,
      currentAgentSteps: [],

      sidebarOpen: true,
      activeTab: 'chat',
      compactMode: false,

      selectedModel: '',
      setSelectedModel: (model) => set({ selectedModel: model }),
      availableModels: [],
      setAvailableModels: (models) => set({ availableModels: models }),

      locale: 'fr',
      setLocale: (locale) => set({ locale }),

      theme: 'dark',
      setTheme: (theme) => {
        set({ theme })
        document.documentElement.className = theme
      },
      toggleTheme: () => set((state) => {
        const next = state.theme === 'dark' ? 'light' : state.theme === 'light' ? 'purple-rain' : state.theme === 'purple-rain' ? 'pro' : 'dark'
        document.documentElement.className = next
        return { theme: next }
      }),

      focusMode: false,
      toggleFocusMode: () => set((state) => ({ focusMode: !state.focusMode })),

      // ==================== DEBUG LOGS ====================
      addDebugLog: (logData) => {
        const newLog: DebugLog = {
          id: `log_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
          timestamp: Date.now(),
          ...logData,
        }

        set((state) => ({
          debugLogs: [...state.debugLogs.slice(-149), newLog],
        }))
      },

      clearDebugLogs: () => set({ debugLogs: [] }),

      setDebugEnabled: (enabled) => set({ isDebugEnabled: enabled }),

      // ==================== AGENT STEPS ====================
      setAgentSteps: (steps) => set({ currentAgentSteps: steps }),

      updateStep: (stepId, updates) =>
        set((state) => ({
          currentAgentSteps: state.currentAgentSteps.map((step) =>
            step.id === stepId ? { ...step, ...updates } : step
          ),
        })),

      clearAgentSteps: () => set({ currentAgentSteps: [] }),

      // ==================== UI ====================
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setActiveTab: (tab) => set({ activeTab: tab }),
      toggleCompactMode: () => set((state) => ({ compactMode: !state.compactMode })),
    }),

    {
      name: 'ui-pro-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        compactMode: state.compactMode,
        isDebugEnabled: state.isDebugEnabled,
        selectedModel: state.selectedModel,
        locale: state.locale,
        theme: state.theme,
      }),
    }
  )
)