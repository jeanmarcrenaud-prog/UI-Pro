'use client'

// UI-Pro Dashboard - ChatGPT quality

import { useState, useCallback } from 'react'
import { ChatContainer } from '@/components/ChatContainer'
import { Sidebar } from '@/components/Sidebar'
import { DebugPanel } from '@/components/DebugPanel'

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
  const [isLoading, setIsLoading] = useState(false)
  const [showDebug, setShowDebug] = useState(true)
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([
    { id: '1', title: 'Analyzing request', status: 'done' },
    { id: '2', title: 'Planning solution', status: 'done' },
    { id: '3', title: 'Executing', status: 'active' },
    { id: '4', title: 'Reviewing', status: 'pending' },
  ])

  const handleNewChat = useCallback(() => {
    setMessages([])
    setAgentSteps([
      { id: '1', title: 'Analyzing request', status: 'pending' },
      { id: '2', title: 'Planning solution', status: 'pending' },
      { id: '3', title: 'Executing', status: 'pending' },
      { id: '4', title: 'Reviewing', status: 'pending' },
    ])
  }, [])

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
          <div>
            <h1 className="text-lg font-semibold text-white">UI-Pro</h1>
            <p className="text-xs text-slate-500">AI Agent Orchestration</p>
          </div>
          <div className="flex items-center gap-2">
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
          </div>
        </header>
        
        {/* Chat */}
        <ChatContainer 
          messages={messages}
          setMessages={setMessages}
          isLoading={isLoading}
          setIsLoading={setIsLoading}
          agentSteps={agentSteps}
        />
      </main>

      {/* Debug Panel */}
      {showDebug && (
        <DebugPanel 
          steps={agentSteps}
          isOpen={showDebug}
          onToggle={() => setShowDebug(false)}
        />
      )}
    </div>
  )
}