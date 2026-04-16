'use client'

// UI-Pro Dashboard - ChatGPT quality

import { useState, useCallback, useEffect } from 'react'
import { ChatContainer } from '@/components/ChatContainer'
import { Sidebar } from '@/components/Sidebar'
import { DebugPanel } from '@/components/DebugPanel'
import { SettingsView } from '@/components/SettingsView'
import { HistoryView } from '@/components/HistoryView'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'

interface AgentStep {
  id: string
  title: string
  detail?: string
  status: 'pending' | 'active' | 'done'
}

export default function Home() {
  const [activeTab, setActiveTab] = useState('chat')
  const [messages, setMessages] = useState<Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp?: string
    status?: 'thinking' | 'streaming' | 'done' | 'error'
  }>>([])
  const [showDebug, setShowDebug] = useState(true)
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([
    { id: '1', title: 'Analyzing request', status: 'pending' },
    { id: '2', title: 'Planning solution', status: 'pending' },
    { id: '3', title: 'Executing', status: 'pending' },
    { id: '4', title: 'Reviewing', status: 'pending' },
  ])
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'error'>('connecting')
  
  const { selectedModel, availableModels } = useUIStore()
  const { isLoading } = useChatStore()

  const handleNewChat = useCallback(() => {
    setMessages([])
    setAgentSteps([
      { id: '1', title: 'Analyzing request', status: 'pending' },
      { id: '2', title: 'Planning solution', status: 'pending' },
      { id: '3', title: 'Executing', status: 'pending' },
      { id: '4', title: 'Reviewing', status: 'pending' },
    ])
    setElapsedSeconds(0)
  }, [])

  // Timer for elapsed time when loading
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (isLoading) {
      interval = setInterval(() => {
        setElapsedSeconds(s => s + 1)
      }, 1000)
    } else {
      setElapsedSeconds(0)
    }
    return () => clearInterval(interval)
  }, [isLoading])

  // Track connection status via WebSocket
  useEffect(() => {
    const ws = new WebSocket(`ws://${typeof window !== 'undefined' ? window.location.hostname : 'localhost'}:8000/ws`)
    
    ws.onopen = () => setConnectionStatus('connected')
    ws.onerror = () => setConnectionStatus('error')
    ws.onclose = () => setConnectionStatus('error')
    
    return () => ws.close()
  }, [])

  const currentStepIdx = agentSteps.findIndex(s => s.status === 'active')
  const modelName = selectedModel || availableModels[0] || 'gemma4'
  
  const debugStatus: 'idle' | 'running' | 'error' = isLoading ? 'running' : 'error' in messages.map(m => m.status) ? 'error' : 'idle'

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-950 to-slate-900">
      <Sidebar 
        activeTab={activeTab} 
        onTabChange={setActiveTab} 
        onNewChat={handleNewChat}
      />
      <main className="flex-1 flex flex-col">
        {/* Header */}
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
          steps={agentSteps}
          isOpen={showDebug}
          onToggle={() => setShowDebug(false)}
          status={debugStatus}
          modelName={modelName}
          currentStep={currentStepIdx >= 0 ? currentStepIdx : 0}
          elapsedSeconds={elapsedSeconds}
          tokenCount={0}
          connectionStatus={connectionStatus}
        />
      )}
    </div>
  )
}