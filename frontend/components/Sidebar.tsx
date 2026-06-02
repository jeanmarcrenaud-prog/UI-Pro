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
  { id: 'chat', label: t.sidebar.chat, icon: '💬', shortcut: 'Alt+1' },
  { id: 'history', label: t.sidebar.history, icon: '📜', shortcut: 'Alt+2' },
  { id: 'settings', label: t.sidebar.settings, icon: '⚙️', shortcut: 'Alt+3' },
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
            isLoaded: m.isLoaded,
            sizeVramGb: m.sizeVramGb,
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
          id: m.name as string,
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
          isLoaded: m.isLoaded as boolean | undefined,
          sizeVramGb: m.sizeVramGb as number | undefined,
        })))
      }
    }
    events.on('modelsDiscovered', handleModelsDiscovered)

    // Use the unified polling service to avoid duplicate timers
    modelDiscovery.startPolling(120_000)

    return () => {
      isMounted = false
      clearTimeout(fallbackTimeout)
      modelDiscovery.stopPolling()
      events.off('modelsDiscovered', handleModelsDiscovered)
    }
  }, [setAvailableModels])

  return (
    <motion.aside
      layout
      className="
        w-64 
        glass-panel
        border-r-0
        flex 
        flex-col
        relative
        z-10
      "
      aria-label="Main navigation sidebar"
    >
      {/* Logo Header */}
      <div className="p-5 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-3">
          <div
            className="
              w-11 h-11 
              rounded-xl 
              bg-gradient-to-br 
              from-violet-600 
              to-fuchsia-600 
              flex items-center 
              justify-center 
              text-white 
              font-bold 
              text-lg 
              shadow-[var(--shadow-md)]
            "
            aria-hidden="true"
          >
            U
          </div>
          <div>
            <h3 className="text-[var(--text-primary)] font-semibold text-sm">
              UI-Pro
            </h3>
            <p className="text-[var(--text-muted)] text-xs">AI Agent System</p>
          </div>
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-4 border-b border-[var(--border-subtle)]">
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
            px-5 py-3.5 
            text-sm 
            font-medium 
            transition-all duration-200 
            flex items-center 
            justify-center 
            gap-2 
            shadow-[var(--shadow-md)] hover:shadow-[var(--shadow-lg)]
            hover:shadow-violet-500/20
            focus:outline-none focus:ring-2 focus:ring-violet-500/50
          "
          aria-label="Create new chat"
        >
<span className="text-lg" aria-hidden="true">+</span>
          {t.sidebar.newChat}
        </button>
      </div>

      {/* Model Selector */}
      <div className="px-4 pb-4 space-y-2">
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
            text-[var(--text-muted)] 
            hover:text-[var(--text-secondary)] 
            flex items-center 
            gap-1.5 
            py-2.5 
            px-2
            rounded-lg 
            hover:bg-[var(--surface-secondary)] 
            transition-colors duration-150
          "
          aria-label="Refresh model list"
        >
          <span className="text-sm" aria-hidden="true">↻</span>
          {t.sidebar.refreshModels}
        </button>
      </div>

      {/* Navigation Tabs */}
      <nav className="px-3 space-y-1.5 mt-1" aria-label="Main navigation">
        {getNavigationTabs(t).map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            title={`${tab.label} (${tab.shortcut})`}
            className={`
              w-full 
              text-left 
              px-4 
              py-3 
              rounded-xl 
              text-sm 
              transition-all duration-200 
              flex items-center 
              gap-3
              group
              relative
              ${
                activeTab === tab.id
                  ? 'bg-[var(--surface-secondary)]/80 text-[var(--text-primary)] shadow-[var(--shadow-sm)]'
                  : 'text-[var(--text-muted)] hover:bg-[var(--surface-secondary)]/50 hover:text-[var(--text-secondary)]'
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

            {/* Shortcut badge */}
            <span className="ml-auto text-[10px] text-[var(--text-muted)]/60 font-mono">{tab.shortcut}</span>

            {/* Active indicator bar */}
            {activeTab === tab.id && (
              <motion.span
                layoutId="active-indicator"
                className="absolute left-0 w-1 h-8 bg-[var(--accent)] rounded-r-full"
                initial={false}
              />
            )}
          </button>
        ))}
      </nav>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto mt-3 px-3">
        <div className="px-3 py-2.5 text-xs text-[var(--text-muted)] font-medium border-b border-[var(--border-subtle)]">
          {t.sidebar.recentChats}
        </div>

        {/* Empty state */}
        {history.length === 0 ? (
          <div className="px-3 py-6 text-xs text-[var(--text-muted)]/60 text-center italic">
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
      <div className="p-4 border-t border-[var(--border-subtle)] text-xs text-[var(--text-muted)] bg-[var(--bg-tertiary)]">
        <div className="flex items-center justify-between mb-2">
          <span>UI-Pro</span>
          <span className="text-[var(--accent)] font-mono font-medium">v1.0</span>
        </div>
        <div className="flex items-center gap-2 text-[var(--text-muted)]/75">
          <span>{availableModels.length} model{availableModels.length !== 1 ? 's' : ''}</span>
          {(() => {
            const loaded = availableModels.filter(m => m.isLoaded).length
            if (loaded > 0) {
              return (
                <span className="flex items-center gap-1.5 text-emerald-400 text-[10px] font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
                  {loaded} in VRAM
                </span>
              )
            }
            return null
          })()}
        </div>
      </div>
    </motion.aside>
  )
}
