// SettingsView.tsx
// Role: Settings page - displays model selector, backend status indicators, system resource metrics,
// and About info - allows model discovery refresh and live backend connectivity checks

'use client'

import { useState, useEffect, useRef } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'
import { modelDiscovery } from '@/services/modelDiscovery'
import { LLM_CONFIG } from '@/lib/config'
import { motion } from 'framer-motion'
import { SystemStats } from './SystemStats'

/**
 * Settings View Component
 * 
 * Displays model configuration, backend status, and system information
 * 
 * @returns React element for settings view
 */

interface BackendItem {
  name: string
  url: string
  status: 'active' | 'inactive' | 'error'
}

interface BackendInfo {
  name: string
  url: string
  status: 'active' | 'inactive' | 'error'
}

export function SettingsView() {
  const { availableModels, selectedModel, setSelectedModel } = useUIStore()
  const [isRefreshLoading, setIsRefreshLoading] = useState(false)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [mounted, setMounted] = useState(false)

  // Initialize on mount
  useEffect(() => {
    setMounted(true)
    setHasLoaded(true)
    // Discover models for first load if not already done
  }, [])

  /**
   * Discover backend statuses dynamically
   */
  const [backendInfo, setBackendInfo] = useState<BackendInfo[]>([
    { name: 'Ollama', url: LLM_CONFIG.ollamaUrl, status: 'inactive' as const },
    { name: 'LM Studio', url: LLM_CONFIG.lmstudioUrl, status: 'inactive' as const },
    { name: 'llama.cpp', url: LLM_CONFIG.llamacppUrl, status: 'inactive' as const },
    { name: 'Lemonade', url: LLM_CONFIG.lemonadeUrl, status: 'inactive' as const },
  ])

  // Test backend connectivity on mount
  useEffect(() => {
    const checkBackends = async () => {
      const results = await Promise.all(
        backendInfo.map(async (backend) => {
          try {
            const response = await fetch(`${backend.url}/api/tags`, {
              signal: AbortSignal.timeout(2000),
            })
            if (response.ok) return { ...backend, status: 'active' as const }
          } catch {
            // Try alternate endpoint
            try {
              const response = await fetch(`${backend.url}/api/v1/models`, {
                signal: AbortSignal.timeout(2000),
              })
              if (response.ok) return { ...backend, status: 'active' as const }
            } catch {}
          }
          return backend
        })
      )
      setBackendInfo(results)
    }
    checkBackends()
  }, [])

  /**
   * Handle model refresh
   */
  const handleRefreshModels = async () => {
    setIsRefreshLoading(true)
    try {
      await modelDiscovery.discover()
    } catch (error) {
      console.error('Failed to discover models:', error)
    } finally {
      setIsRefreshLoading(false)
    }
  }

  /**
   * Format backend status icon and text
   */
  const getStatusBadge = (status: BackendInfo['status']) => {
    const style =
      status === 'active'
        ? 'text-emerald-400'
        : 'text-slate-500'
    const dotColor =
      status === 'active'
        ? 'bg-emerald-400'
        : 'bg-slate-600'
    const label =
      status === 'active'
        ? { text: 'Active', icon: '●' }
        : { text: 'Inactive', icon: '○' }

    return (
      <div
        className={`
          flex items-center 
          gap-1.5 
          text-xs 
          font-mono
          ${style}
        `}
        role="status"
        aria-live="polite"
      >
        <span className={`w-3 h-3 rounded-full ${dotColor}`} />
        <span className="capitalize">{label.text}</span>
      </div>
    )
  }

  /**
   * Format model count info
   */
  const modelCount = availableModels.length
  const modelsPlural = modelCount !== 1 ? 'models' : 'model'

  if (!mounted) return null

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className="flex-1 p-6 overflow-y-auto"
    >
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-white mb-2">
          Settings
        </h2>
        <p className="text-sm text-slate-500">
          Configure AI models and backend connections
        </p>
      </div>

      {/* Section: Model Settings */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-slate-400 mb-4 flex items-center gap-2">
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
          Models
        </h3>

        <div className="bg-slate-800/50 rounded-xl p-5 space-y-5 border border-slate-800/60">
          {/* Default Model Selector */}
          <div className="space-y-2">
            <label
              htmlFor="default-model"
              className="
                text-xs 
                text-slate-400 
                font-medium 
                uppercase 
                tracking-wide
              "
            >
              Default Model
            </label>
            <div className="relative">
              <select
                id="default-model"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="
                  appearance-none 
                  w-full 
                  bg-slate-700/80 
                  border border-slate-600 
                  text-white 
                  rounded-lg 
                  px-4 py-2.5 pr-10 
                  focus:outline-none 
                  focus:border-violet-500 
                  focus:ring-2 
                  focus:ring-violet-500/20 
                  transition-all duration-150
                "
                aria-label="Select default model"
              >
                {availableModels.length === 0 ? (
                  <option value="" disabled>No models found</option>
                ) : (
                  availableModels.map((model) => (
                    <option
                      key={model}
                      value={model}
                    >
                      {model}
                    </option>
                  ))
                )}
              </select>

              {/* Dropdown indicator */}
              <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                <svg
                  className="w-4 h-4 text-slate-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>
            </div>

            {/* Help text */}
            <p className="text-xs text-slate-500">
              This model will be used for all new chats
            </p>
          </div>

          {/* Model information */}
          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-3">
              <div
                className="
                  w-8 h-8 
                  rounded-lg 
                  bg-gradient-to-br 
                  from-violet-600 
                  to-fuchsia-600 
                  flex items-center 
                  justify-center
                  text-white
                  text-xs
                  font-semibold
                "
              >
                M
              </div>
              <div>
                <p className="text-sm text-white font-medium">
                  Available Models
                </p>
                <p className="text-xs text-slate-500">
                  {modelCount} {modelsPlural} discovered
                </p>
              </div>
            </div>

            {/* Refresh button */}
            <motion.button
              onClick={handleRefreshModels}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              disabled={isRefreshLoading}
              className="
                flex 
                items-center 
                gap-1.5 
                bg-violet-600 
                hover:bg-violet-700 
                disabled:from-violet-800 
                disabled:cursor-not-allowed 
                text-white 
                text-sm 
                px-4 py-2.5 
                rounded-lg 
                transition-all duration-150
                focus:outline-none focus:ring-2 focus:ring-violet-500/50
              "
              aria-label={isRefreshLoading ? 'Refreshing models...' : 'Refresh model list'}
            >
              {isRefreshLoading ? (
                <motion.span
                  animate={{ rotate: 360 }}
                  transition={{
                    repeat: Infinity,
                    duration: 1,
                    ease: 'linear'
                  }}
                  className="w-4 h-4 border border-white/30 border-t-white rounded-full"
                />
              ) : (
                <>
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  Refresh
                </>
              )}
            </motion.button>
          </div>
        </div>
      </section>

      {/* Section: Backend Status */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-slate-400 mb-4 flex items-center gap-2">
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
            />
          </svg>
          Backend Connections
        </h3>

        <div className="bg-slate-800/50 rounded-xl p-5 space-y-3 border border-slate-800/60">
          {backendInfo.map((backend) => (
            <div
              key={backend.name}
              className="
                flex 
                items-center 
                justify-between 
                p-3 
                rounded-lg 
                hover:bg-slate-800/80 
                transition-colors duration-150
              "
            >
              <div className="flex items-center gap-3">
                {/* Backend icon */}
                <div
                  className={`
                    w-8 h-8 
                    rounded-lg 
                    flex items-center 
                    justify-center
                    ${
                      backend.status === 'active'
                        ? 'bg-emerald-900/30 text-emerald-400'
                        : 'bg-slate-800 text-slate-500'
                    }
                  `}
                >
                  {backend.name === 'Ollama' ? '🦙' : '🖥️'}
                </div>

                {/* Backend info */}
                <div>
                  <p className="text-sm text-white font-medium">
                    {backend.name}
                  </p>
                  <p className="text-xs text-slate-500 font-mono break-all">
                    {backend.url.split('://')[1]}
                  </p>
                </div>
              </div>

              {/* Status badge */}
              {getStatusBadge(backend.status)}
            </div>
          ))}
        </div>
      </section>

      {/* Section: System Stats */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-slate-400 mb-4 flex items-center gap-2">
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          System Resources
        </h3>

        <SystemStats />
      </section>

      {/* Section: About */}
      <section>
        <h3 className="text-sm font-semibold text-slate-400 mb-4 flex items-center gap-2">
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          About
        </h3>

        <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-800/60">
          <div className="space-y-3">
            <div>
              <p className="text-sm text-white font-semibold">
                UI-Pro
              </p>
              <p className="text-xs text-slate-400">AI Agent Orchestration System</p>
            </div>

            <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between">
              <div className="text-slate-500">
                <span className="text-xs">Version</span>
                <span className="ml-2 text-slate-400">1.0.0</span>
              </div>
              <span className="text-xs text-slate-500">
                {hasLoaded ? 'Loaded' : 'Loading...'}
              </span>
            </div>

            <div>
              <p className="text-xs text-slate-500">
                Powered by{' '}
                <span className="text-violet-400">Ollama</span>{' '}
                <span className="ml-1.5">+</span>{' '}
                <span className="text-violet-400">Next.js</span>
              </p>
            </div>

            {modelCount > 0 && (
              <div className="pt-3 border-t border-slate-800/60">
                <p className="text-xs text-slate-500">
                  Last updated:{' '}
                  <span className="text-slate-400 font-mono">
                    {new Date().toLocaleDateString()}
                  </span>
                </p>
              </div>
            )}
          </div>
        </div>
      </section>
    </motion.div>
  )
}
