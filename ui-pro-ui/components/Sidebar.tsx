'use client'

// UI-Pro Sidebar - ChatGPT quality with dynamic models

import { useState, useEffect } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { modelDiscovery } from '@/services/modelDiscovery'
import { motion } from 'framer-motion'

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
  onNewChat?: () => void
}

const tabs = [
  { id: 'chat', label: 'Chat', icon: '💬' },
  { id: 'history', label: 'History', icon: '📜' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
]

export function Sidebar({ activeTab, onTabChange, onNewChat }: SidebarProps) {
  const { 
    availableModels, 
    selectedModel, 
    setSelectedModel 
  } = useUIStore()
  const { history, loadChat, deleteChat } = useChatStore()
  const [isLoadingModels, setIsLoadingModels] = useState(true)

  // Discover models on mount
  useEffect(() => {
    const loadModels = async () => {
      setIsLoadingModels(true)
      try {
        await modelDiscovery.discover()
      } catch (error) {
        console.error('Failed to discover models:', error)
      } finally {
        setIsLoadingModels(false)
      }
    }
    
    loadModels()
    
    // Poll for model updates every 60s
    modelDiscovery.startPolling(60000)
    
    return () => modelDiscovery.stopPolling()
  }, [])

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col">
      {/* Logo */}
      <div className="p-4 flex items-center justify-center">
        <img src="/logo.png" alt="UI-Pro" className="h-12 w-auto" />
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full bg-violet-600 hover:bg-violet-700 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors flex items-center gap-2"
        >
          <span>+</span> New Chat
        </button>
      </div>

      {/* Model Selector */}
      <div className="px-3 pb-3">
        <div className="relative">
          {isLoadingModels ? (
            <div className="w-full bg-slate-800 border border-slate-700 text-slate-400 text-xs rounded-lg px-3 py-2 flex items-center gap-2">
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1 }}
                className="w-3 h-3 border border-slate-400 border-t-transparent rounded-full"
              />
              Discovering models...
            </div>
          ) : (
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500"
            >
              {availableModels.length === 0 ? (
                <option key="no-models" value="">No models found</option>
              ) : (
                availableModels.map((model) => (
                  <option key={model || 'empty'} value={model}>
                    {model}
                  </option>
                ))
              )}
            </select>
          )}
        </div>
        <button
          onClick={() => modelDiscovery.discover()}
          className="text-xs text-slate-500 hover:text-slate-400 mt-1 flex items-center gap-1"
        >
          <span>↻</span> Refresh models
        </button>
      </div>

      {/* Navigation */}
      <nav className="px-2 space-y-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
              activeTab === tab.id
                ? 'bg-slate-800 text-white'
                : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
            }`}
          >
            <span className="mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto mt-4 px-2">
        <div className="text-xs text-slate-500 px-3 py-2">Recent Chats</div>
        {history.length === 0 ? (
          <div className="text-xs text-slate-600 px-3 py-2">No chats yet</div>
        ) : (
          history.slice(0, 10).map((chat) => (
            <button
              key={chat.id}
              onClick={() => {
                loadChat(chat.id)
                onTabChange('chat')
              }}
              className="w-full text-left px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-slate-800/50 hover:text-white transition-colors"
            >
              <div className="truncate">{chat.title}</div>
              <div className="text-xs text-slate-600">
                {new Date(chat.updatedAt).toLocaleDateString()}
              </div>
            </button>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800 text-xs text-slate-500">
        <div>UI-Pro v1.0</div>
        <div className="text-slate-600 mt-1">
          {availableModels.length} model{availableModels.length !== 1 ? 's' : ''} available
        </div>
      </div>
    </aside>
  )
}