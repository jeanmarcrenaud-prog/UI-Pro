'use client'

import { useState, useEffect, useRef } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { modelDiscovery } from '@/services/modelDiscovery'
import { motion, AnimatePresence } from 'framer-motion'

/**
 * Sidebar Component
 * 
 * Provides navigation, model selection, and chat history access
 * 
 * @param activeTab - Currently active tab ('chat', 'history', 'settings')
 * @param onTabChange - Callback when tab changes
 * @param onNewChat - Optional callback to create new chat
 */

interface Tab {
  id: string
  label: string
  icon: string
}

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
  onNewChat?: () => void
}

// Data: Navigation tabs configuration
const NAVIGATION_TABS: readonly Tab[] = [
  { id: 'chat', label: 'Chat', icon: '💬' },
  { id: 'history', label: 'History', icon: '📜' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
] as const

// Component: LoadingIndicator
// Displays loading state for model discovery
function LoadingIndicator() {
  return (
    <div
      className="
        w-full 
        bg-slate-800/80 
        border border-slate-700/60 
        text-slate-400 
        text-xs 
        rounded-xl 
        px-3 py-2.5 
        flex items-center 
        justify-between
        gap-1.5
      "
      role="status"
      aria-live="polite"
    >
      <motion.span
        animate={{ rotate: 360 }}
        transition={{
          repeat: Infinity,
          duration: 1,
          ease: 'linear'
        }}
        className="w-3 h-3 border border-slate-400 border-t-transparent rounded-full"
      />
      <span className="flex items-center gap-1.5">
        Discovering models
        <motion.span
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{
            repeat: Infinity,
            duration: 1.4,
            repeatDelay: 0.2
          }}
          className="text-slate-600 text-[10px]"
        >
          ↻
        </motion.span>
      </span>
    </div>
  )
}

// Component: ModelSelectDropdown
// Dropdown component for model selection
function ModelSelectDropdown({
  isLoading,
  availableModels,
  selectedModel,
  onModelChange
}: {
  isLoading: boolean
  availableModels: string[]
  selectedModel: string
  onModelChange: (model: string) => void
}) {
  return (
    <div className="relative">
      <AnimatePresence>
        {isLoading ? (
          <LoadingIndicator />
        ) : (
          <select
            value={selectedModel}
            onChange={(e) => onModelChange(e.target.value)}
            className="
              appearance-none 
              w-full 
              bg-slate-800/80 
              border border-slate-700/60 
              text-slate-200 
              text-xs 
              rounded-xl 
              px-3 py-2.5 
              focus:outline-none 
              focus:border-violet-500/60 
              focus:ring-2 
              focus:ring-violet-500/20 
              transition-all duration-200
              pr-16
            "
            aria-label="Select language model"
            aria-describedby="model-help"
          >
            {availableModels.length === 0 ? (
              <option value="" disabled>
                No models found
              </option>
            ) : (
              availableModels.map((model) => (
                <option
                  key={model}
                  value={model}
                  disabled={model === ''}
                >
                  {model}
                </option>
              ))
            )}
          </select>
        )}
      </AnimatePresence>

      {/* Help text */}
      <span
        id="model-help"
        className="
          absolute 
          right-3 
          top-1/2 
          -translate-y-1/2 
          text-xs 
          text-slate-500 
          pointer-events-none
        "
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </span>
    </div>
  )
}

// Component: ChatHistoryItem
// Renders a single chat history entry
function ChatHistoryItem({
  chat,
  onClick
}: {
  chat: any
  onClick: () => void
}) {
  const updatedAt = new Date(chat.updatedAt)
  const dateStr = updatedAt.toLocaleDateString()
  const timeStr = updatedAt.toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit' 
  })

  return (
    <button
      onClick={onClick}
      className="
        w-full 
        text-left 
        px-3 
        py-2.5 
        rounded-xl 
        text-sm 
        text-slate-400 
        hover:bg-slate-800/50 
        hover:text-slate-200 
        transition-all duration-150 
        group
        truncate
      "
    >
      <div
        className="
          truncate 
          font-medium 
          group-hover:text-slate-200
          transition-colors duration-150
        "
        title={chat.title}
      >
        {chat.title}
      </div>
      <div className="text-[10px] text-slate-600 mt-0.5">
        {dateStr} • {timeStr}
      </div>
    </button>
  )
}

export function Sidebar({ activeTab, onTabChange, onNewChat }: SidebarProps) {
  const {
    availableModels,
    selectedModel,
    setSelectedModel
  } = useUIStore()

  const { history, loadChat, deleteChat } = useChatStore()

  const [isLoadingModels, setIsLoadingModels] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Discover models on mount
  useEffect(() => {
    let isMounted = true
    
    const initModels = async () => {
      try {
        await modelDiscovery.discover()
      } catch (error) {
        console.error('Failed to discover models:', error)
      } finally {
        if (isMounted) {
          setIsLoadingModels(false)
        }
      }
    }

    // Set loading false after 5s timeout as fallback
    const fallbackTimeout = setTimeout(() => {
      if (isMounted) {
        setIsLoadingModels(false)
        setIsRefreshing(false)
      }
    }, 5000)

    initModels()

    // Poll for model updates every 30s
    const pollInterval = setInterval(async () => {
      try {
        setIsRefreshing(true)
        await modelDiscovery.discover()
      } catch (error) {
        console.error('Failed to poll models:', error)
      } finally {
        setIsRefreshing(false)
      }
    }, 30000)

    return () => {
      isMounted = false
      clearTimeout(fallbackTimeout)
      clearInterval(pollInterval)
      modelDiscovery.stopPolling()
    }
  }, [])

  return (
    <aside
      className="
        w-64 
        bg-slate-900/50 
        border-r 
        border-slate-800/60 
        flex 
        flex-col
      "
      aria-label="Main navigation sidebar"
    >
      {/* Logo Header */}
      <div className="p-4 border-b border-slate-800/60">
        <div className="flex items-center gap-3">
          <div
            className="
              w-10 h-10 
              rounded-xl 
              bg-gradient-to-br 
              from-violet-600 
              to-fuchsia-600 
              flex items-center 
              justify-center 
              text-white 
              font-bold 
              text-lg 
              shadow-lg
            "
            aria-hidden="true"
          >
            U
          </div>
          <div>
            <h3 className="text-white font-semibold text-sm">
              UI-Pro
            </h3>
            <p className="text-slate-500 text-xs">AI Agent System</p>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-3 border-b border-slate-800/60">
        <button
          onClick={onNewChat}
          className="
            w-full 
            bg-gradient-to-r 
            from-violet-600 
            to-fuchsia-600 
            hover:from-violet-700 
            hover:to-fuchsia-700 
            text-white 
            rounded-xl 
            px-4 py-3 
            text-sm 
            font-medium 
            transition-all duration-200 
            flex items-center 
            justify-center 
            gap-2 
            shadow-lg hover:shadow-violet-500/25
            focus:outline-none focus:ring-2 focus:ring-violet-500/50
          "
          aria-label="Create new chat"
        >
          <span className="text-lg" aria-hidden="true">+</span>
          New Chat
        </button>
      </div>

      {/* Model Selector */}
      <div className="px-3 pb-3 space-y-2">
        <ModelSelectDropdown
          isLoading={isLoadingModels || isRefreshing}
          availableModels={availableModels}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
        />
        <button
          onClick={() => {
            setIsRefreshing(true)
            modelDiscovery.discover().finally(() => {
              setIsRefreshing(false)
            })
          }}
          className="
            text-xs 
            text-slate-500 
            hover:text-slate-400 
            flex items-center 
            gap-1.5 
            py-2 
            rounded-lg 
            hover:bg-slate-800 
            transition-colors duration-150
          "
          aria-label="Refresh model list"
        >
          <span className="text-sm" aria-hidden="true">↻</span>
          Refresh models
        </button>
      </div>

      {/* Navigation Tabs */}
      <nav className="px-2 space-y-1" aria-label="Main navigation">
        {NAVIGATION_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`
              w-full 
              text-left 
              px-3 
              py-2.5 
              rounded-xl 
              text-sm 
              transition-all duration-200 
              flex items-center 
              gap-3
              ${
                activeTab === tab.id
                  ? 'bg-slate-800/80 text-white shadow-sm'
                  : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
              }
            `}
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
          >
            <span
              className="text-lg" 
              aria-hidden="true"
            >
              {tab.icon}
            </span>
            <span
              className={
                activeTab === tab.id
                  ? 'font-medium'
                  : ''
              }
            >
              {tab.label}
            </span>

            {/* Active indicator bar */}
            {activeTab === tab.id && (
              <motion.span
                layoutId="active-indicator"
                className="absolute left-0 w-1 h-8 bg-violet-500 rounded-r-full"
                style={{ top: 4 }}
                initial={false}
              />
            )}
          </button>
        ))}
      </nav>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto mt-2 px-2">
        <div className="px-3 py-2 text-xs text-slate-500 font-medium border-b border-slate-800/60">
          Recent Chats
        </div>

        {/* Empty state */}
        {history.length === 0 ? (
          <div className="px-3 py-4 text-xs text-slate-600 text-center italic">
            No chats yet. Start a new one!
          </div>
        ) : (
          /* History items */
          history
            .slice(0, 10)
            .map((chat) => (
              <ChatHistoryItem
                key={chat.id}
                chat={chat}
                onClick={() => {
                  loadChat(chat.id)
                  onTabChange('chat')
                }}
              />
            ))
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-slate-800/60 text-xs text-slate-500 bg-slate-900/30">
        <div className="flex items-center justify-between mb-1">
          <span>UI-Pro</span>
          <span className="text-violet-400 font-mono">v1.0</span>
        </div>
        <div className="text-slate-600">
          {availableModels.length} model{availableModels.length !== 1 ? 's' : ''} • Ollama 🦙
        </div>
      </div>
    </aside>
  )
}
