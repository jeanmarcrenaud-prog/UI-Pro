// page.tsx (app/)
// Role: Main dashboard page - renders the full UI with Sidebar, ChatContainer, DebugPanel, HistoryView,
// and SettingsView based on active tab, with model logging and elapsed time timer

'use client'

// UI-Pro Dashboard - ChatGPT quality

import { useState, useCallback, useEffect, useRef } from 'react'
import { ChatContainer } from '@/components/ChatContainer'
import { CommandPalette, useKeyboardShortcuts } from '@/components/CommandPalette'
import { Sidebar } from '@/components/Sidebar'
import { DebugPanel } from '@/components/DebugPanel'
import { SettingsView } from '@/components/SettingsView'
import { HistoryView } from '@/components/HistoryView'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'

export default function Home() {
  const [activeTab, setActiveTab] = useState('chat')
  const [showDebug, setShowDebug] = useState(true)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const hasLoggedModel = useRef(false) // Stable ref - persists across renders
  const { paletteOpen, setPaletteOpen } = useKeyboardShortcuts()
  
  // Stores (MUST come first - isLoading is used below)
  const { selectedModel, availableModels, focusMode, sidebarOpen } = useUIStore()
  const { isLoading, logs, tokenCount, clearMessages, messages } = useChatStore()
  const { steps: storeSteps, currentStep: storeCurrentStep } = useAgentStore()

  const handleNewChat = useCallback(() => {
    clearMessages()
    setElapsedSeconds(0)
  }, [clearMessages])

  // Timer for elapsed time when loading
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null

    if (isLoading) {
      if (!hasLoggedModel.current) {
        hasLoggedModel.current = true

        const currentModel =
          selectedModel ??
          (availableModels.length > 0 ? availableModels[0] : 'unknown')

        useChatStore.getState().addLog(`🤖 Using model: ${currentModel}`)
      }

      interval = setInterval(() => {
        setElapsedSeconds(s => s + 1)
      }, 1000)
    } else {
      hasLoggedModel.current = false // Reset for next time
      setElapsedSeconds(0)
    }

    // ALWAYS cleanup - runs on unmount OR deps change
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isLoading, selectedModel, availableModels])

  // Build model display name with provider info
  const currentModelInfo = availableModels.find(m => m.name === selectedModel) 
    || availableModels[0]
  const modelName = currentModelInfo 
    ? `${currentModelInfo.name} • ${currentModelInfo.provider}`
    : (selectedModel ?? 'unknown')
    
  const hasError = messages.some(m => m.status === 'error')
  const debugStatus: 'idle' | 'running' | 'error' = isLoading ? 'running' : hasError ? 'error' : 'idle'

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-950 to-slate-900">
      {/* Sidebar - hidden in focus mode */}
      {!focusMode && (
<Sidebar 
          activeTab={activeTab} 
          onTabChange={setActiveTab} 
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
          <div className="flex items-center gap-2">
            {activeTab === 'chat' && (
              <button
                onClick={() => setShowDebug(!showDebug)}
                className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  showDebug 
                    ? 'bg-violet-600 text-white' 
                    : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                🔧 Debug
              </button>
            )}
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

      {/* Debug Panel */}
      {activeTab === 'chat' && showDebug && (
        <DebugPanel 
          steps={storeSteps}
          isOpen={showDebug}
          onToggle={() => setShowDebug(false)}
          onClearLogs={() => useChatStore.getState().clearLogs()}
          status={debugStatus}
          modelName={modelName}
          elapsedSeconds={elapsedSeconds}
          tokenCount={tokenCount}
          connectionStatus={isLoading ? 'connecting' : 'connected'}
          logs={logs}
        />
      )}

      {/* Command Palette */}
      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}