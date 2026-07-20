// page.tsx (app/)
// Role: Main dashboard page - renders the full UI with Sidebar, ChatContainer, HistoryView,
// and SettingsView based on active tab, with model logging and elapsed time timer

'use client'

// UI-Pro Dashboard - ChatGPT quality

import { useState, useCallback, useEffect, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu, X } from 'lucide-react'
import { ChatContainer } from '@/components/ChatContainer'
import { AgentCanvas } from '@/components/agent/AgentCanvas'
import { CommandPalette, useKeyboardShortcuts } from '@/components/CommandPalette'
import { Sidebar } from '@/components/Sidebar'

import { SettingsView } from '@/components/SettingsView'
import { HistoryView } from '@/components/HistoryView'
import { MarioView } from '@/components/MarioView'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { useResponsive } from '@/lib/hooks/useResponsive'

// Expose stores for e2e testing
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  import('@/lib/stores/agentStore').then(m => {
    (window as any).__TEST_AGENT_STORE__ = m.useAgentStore
  })
  import('@/lib/stores/chatStore').then(m => {
    (window as any).__TEST_CHAT_STORE__ = m.useChatStore
  })
  import('@/services/chatService').then(m => {
    (window as any).__TEST_CHAT_SERVICE__ = m.chatService
  })
  import('@/lib/events').then(m => {
    (window as any).__TEST_EVENTS__ = m.events
  })
}

type TabType = 'chat' | 'history' | 'settings' | 'canvas' | 'mario'

export default function Home() {
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const hasLoggedModel = useRef(false)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const { paletteOpen, setPaletteOpen } = useKeyboardShortcuts()
  const { isSmall } = useResponsive()
  
  // Store selectors - more efficient than getState()
  const { selectedModel, availableModels, focusMode, activeTab, setActiveTab, sidebarOpen, toggleSidebar } = useUIStore()
  const isLoading = useChatStore(state => state.isLoading)
  const clearMessages = useChatStore(state => state.clearMessages)
  const addLog = useChatStore(state => state.addLog)
  const clearLogs = useChatStore(state => state.clearLogs)

  const handleNewChat = useCallback(() => {
    clearMessages()
    setElapsedSeconds(0)
  }, [clearMessages])

  const onTabChange = useCallback((tab: TabType) => {
    setActiveTab(tab)
  }, [setActiveTab])

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

  return (
    <div className="flex h-screen bg-[var(--bg-primary)] theme-transition">
      {/* Sidebar - Desktop: side by side | Small screens: overlay */}
      {!focusMode && (
        <>
          {/* Desktop sidebar */}
          {!isSmall && (
            <motion.div
              animate={{ width: sidebarOpen ? 256 : 0, opacity: sidebarOpen ? 1 : 0 }}
              transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
              className="overflow-hidden shrink-0"
            >
              <div className="w-64">
                <Sidebar
                  activeTab={activeTab}
                  onTabChange={onTabChange}
                  onNewChat={handleNewChat}
                />
              </div>
            </motion.div>
          )}

          {/* Mobile/Tablet overlay sidebar */}
          <AnimatePresence>
            {isSmall && sidebarOpen && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
                onClick={toggleSidebar}
              >
                <motion.aside
                  initial={{ x: -280 }}
                  animate={{ x: 0 }}
                  exit={{ x: -280 }}
                  transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
                  className="absolute left-0 top-0 bottom-0 w-64"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Sidebar
                    activeTab={activeTab}
                    onTabChange={(tab) => { onTabChange(tab); toggleSidebar() }}
                    onNewChat={() => { handleNewChat(); toggleSidebar() }}
                  />
                </motion.aside>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
      
      {/* Main Content - full width in focus mode */}
      <main className={`flex-1 flex flex-col min-w-0 ${focusMode ? 'w-full' : ''}`}>
        {/* Header - hidden in focus mode */}
        {!focusMode && (
          <header className="px-6 py-4 border-b border-[var(--border-subtle)] theme-transition flex items-center justify-between gap-4 shadow-[var(--shadow-sm)]">
          <div className="flex items-center gap-4 min-w-0">
            {/* Hamburger - visible on small screens or when sidebar is collapsed */}
            <button
              onClick={toggleSidebar}
              className="p-2 rounded-lg hover:bg-[var(--surface-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors shrink-0"
              aria-label="Toggle sidebar"
            >
              {sidebarOpen && isSmall ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <img src="/logo.png" alt="UI-Pro" className="h-9 w-auto shrink-0" />
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-[var(--text-primary)] tracking-tight">UI-Pro</h1>
              <p className="text-xs text-[var(--text-muted)] truncate">AI Agent Orchestration</p>
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
        ) : activeTab === 'mario' ? (
          <MarioView />
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