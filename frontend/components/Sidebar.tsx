// Sidebar.tsx
// Role: Main sidebar - provides navigation tabs (Chat/History/Settings), model selector dropdown with
// discovery, new chat button, recent chat history list, and footer with model count

'use client'

import { useState, useEffect } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { useI18n } from '@/lib/i18n'
import { modelDiscovery } from '@/services/modelDiscovery'
import { events } from '@/lib/events'
import { motion } from 'framer-motion'
import { ModelSelectDropdown } from './sidebar/ModelSelectDropdown'
import { SidebarChatItem } from './sidebar/SidebarChatItem'

/**
 * Sidebar Component
 * 
 * Provides navigation, model selection, and chat history access
 * 
 * @param activeTab - Currently active tab ('chat', 'history', 'settings')
 * @param onTabChange - Callback when tab changes
 * @param onNewChat - Optional callback to create new chat
 */

type TabType = 'chat' | 'history' | 'settings'

interface SidebarProps {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
  onNewChat?: () => void
}

import type { Translations } from '@/lib/i18n'
import type { ModelInfo } from './sidebar/ModelSelectDropdown'

const getNavigationTabs = (t: Translations) => [
  { id: 'chat', label: t.sidebar.chat, icon: '💬' },
  { id: 'history', label: t.sidebar.history, icon: '📜' },
  { id: 'settings', label: t.sidebar.settings, icon: '⚙️' },
] as const

export function Sidebar({ activeTab, onTabChange, onNewChat }: SidebarProps) {
  const {
    availableModels,
    selectedModel,
    setSelectedModel
  } = useUIStore()

  const { history, loadChat } = useChatStore()
  const { t } = useI18n()

  const [isLoadingModels, setIsLoadingModels] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Discover models on mount
  const { setAvailableModels } = useUIStore()
  
  useEffect(() => {
    let isMounted = true
    
    const initModels = async () => {
      try {
        const models = await modelDiscovery.discover()
        // Update store with discovered models including rich metadata
        if (isMounted && models.length > 0) {
          const mappedModels: ModelInfo[] = models.map(m => ({
            id: m.id,
            name: m.name,
            provider: m.provider,
            parameterSize: m.parameterSize,
            quantization: m.quantization,
            sizeGb: m.sizeGb,
            maxContext: m.maxContext,
            speedTier: m.speedTier,
            isCoder: m.isCoder,
            isReasoning: m.isReasoning,
            isVision: m.isVision,
            capabilities: m.capabilities,
          }))
          setAvailableModels(mappedModels)
        }
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

    // Listen for model discovery events to update store
    const handleModelsDiscovered = (data: { models: Array<Record<string, unknown>> }) => {
      if (data.models && data.models.length > 0) {
        setAvailableModels(data.models.map(m => ({ 
          id: `${m.provider}-${m.name}` as string,
          name: m.name as string, 
          provider: m.provider as 'ollama' | 'lmstudio' | 'lemonade',
          parameterSize: m.parameterSize as string | undefined,
          quantization: m.quantization as string | undefined,
          sizeGb: m.sizeGb as number | undefined,
          maxContext: m.maxContext as number | undefined,
          speedTier: m.speedTier as 'very_fast' | 'fast' | 'medium' | 'slow' | undefined,
          isCoder: m.isCoder as boolean | undefined,
          isReasoning: m.isReasoning as boolean | undefined,
          isVision: m.isVision as boolean | undefined,
          capabilities: m.capabilities as string[] | undefined,
        })))
      }
    }
    events.on('modelsDiscovered', handleModelsDiscovered)

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
      events.off('modelsDiscovered', handleModelsDiscovered)
    }
  }, [setAvailableModels])

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
          {t.sidebar.newChat}
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
          {t.sidebar.refreshModels}
        </button>
      </div>

      {/* Navigation Tabs */}
      <nav className="px-2 space-y-1" aria-label="Main navigation">
        {getNavigationTabs(t).map((tab) => (
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
          {t.sidebar.recentChats}
        </div>

        {/* Empty state */}
        {history.length === 0 ? (
          <div className="px-3 py-4 text-xs text-slate-600 text-center italic">
            {t.sidebar.noChatsYet}
          </div>
        ) : (
          /* History items */
          history
            .slice(0, 10)
            .map((chat) => (
              <SidebarChatItem
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
          {availableModels.length} model{availableModels.length !== 1 ? 's' : ''} • {t.sidebar.ollama} 🦙
        </div>
      </div>
    </aside>
  )
}
