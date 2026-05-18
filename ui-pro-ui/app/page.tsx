// page.tsx (app/)
// Role: Main dashboard page - renders the full UI with Sidebar, ChatContainer, HistoryView,
// and SettingsView based on active tab, with model logging and elapsed time timer

'use client'

// UI-Pro Dashboard - ChatGPT quality

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { ChatContainer } from '@/components/ChatContainer'
import { CommandPalette, useKeyboardShortcuts } from '@/components/CommandPalette'
import { Sidebar } from '@/components/Sidebar'

import { SettingsView } from '@/components/SettingsView'
import { HistoryView } from '@/components/HistoryView'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'

type TabType = 'chat' | 'history' | 'settings'

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>('chat')
  
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const hasLoggedModel = useRef(false)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const { paletteOpen, setPaletteOpen } = useKeyboardShortcuts()
  
  // Store selectors - more efficient than getState()
  const { selectedModel, availableModels, focusMode } = useUIStore()
  const isLoading = useChatStore(state => state.isLoading)
  const logs = useChatStore(state => {
    const logsStore = state.logs
    // Handle CircularBuffer: extract array
    return Array.isArray(logsStore) ? logsStore : logsStore.getAll?.() || []
  })
  const tokenCount = useChatStore(state => state.tokenCount)
  const currentCode = useChatStore(state => state.currentCode)
  const messages = useChatStore(state => state.messages)
  const clearMessages = useChatStore(state => state.clearMessages)
  const addLog = useChatStore(state => state.addLog)
  const clearLogs = useChatStore(state => state.clearLogs)
  
  const storeSteps = useAgentStore(state => state.steps)

  const handleNewChat = useCallback(() => {
    clearMessages()
    setElapsedSeconds(0)
  }, [clearMessages, setElapsedSeconds])

  const onTabChange = useCallback((tab: TabType) => {
    setActiveTab(tab)
  }, [])

  // Memoized model info
  const currentModelInfo = useMemo(() => {
    return availableModels.find(m => m.name === selectedModel) || availableModels[0]
  }, [availableModels, selectedModel])

  const modelName = currentModelInfo 
    ? `${currentModelInfo.name} • ${currentModelInfo.provider}`
    : (selectedModel ?? 'unknown')
  const backend = currentModelInfo?.provider || 'ollama'

  // Effect for model logging
  useEffect(() => {
    if (isLoading && !hasLoggedModel.current) {
      hasLoggedModel.current = true
      const currentModel = selectedModel ?? availableModels[0]?.name ?? 'unknown'
      addLog(`🤖 Using model: ${currentModel}`)
    } else if (!isLoading) {
      hasLoggedModel.current = false
    }
  }, [isLoading, selectedModel, availableModels, addLog])

  // Effect for timer
  useEffect(() => {
    if (isLoading) {
      timerRef.current = setInterval(() => {
        setElapsedSeconds(s => s + 1)
      }, 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
      setElapsedSeconds(0)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isLoading])

const handleClearLogs = useCallback(() => {
    clearLogs()
  }, [clearLogs])

  const handleDebugToggle = useCallback(() => {
    setShowDebug(prev => !prev)
  }, [])

  const hasError = messages.some(m => m.status === 'error')
  const debugStatus: 'idle' | 'running' | 'error' = isLoading ? 'running' : hasError ? 'error' : 'idle'

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-950 to-slate-900">
      {/* Sidebar - hidden in focus mode */}
      {!focusMode && (
<Sidebar 
          activeTab={activeTab} 
          onTabChange={onTabChange} 
          onNewChat={handleNewChat}
        />
      )}
      
      {/* Main Content - full width in focus mode */}
      <main className={`flex-1 flex flex-col ${focusMode ? 'w-full' : ''}`}>
        {/* Header - hidden in focus mode */}
        {!focusMode && (
          <header className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="UI-Pro" className="h-8 w-auto" />
            <div>
              <h1 className="text-lg font-semibold text-white">UI-Pro</h1>
              <p className="text-xs text-slate-500">AI Agent Orchestration</p>
            </div>
          </div>
          
        </header>
        )}
        
        {/* Content based on active tab */}
        {activeTab === 'chat' ? (
          <ChatContainer />
        ) : activeTab === 'history' ? (
          <HistoryView 
            onSelectChat={(id) => {
              // Load chat and switch to chat tab
              setActiveTab('chat')
            }} 
          />
        ) : activeTab === 'settings' ? (
          <SettingsView />
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-400">
            Coming soon...
          </div>
        )}
      </main>

      {/* Command Palette */}
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}