// SettingsView.tsx
// Role: Settings page - displays model selector, backend status indicators, system resource metrics,
// language selector, and About info

'use client'

import { useState, useEffect } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'
import { modelDiscovery } from '@/services/modelDiscovery'
import { LLM_CONFIG } from '@/lib/config'
import { motion } from 'framer-motion'
import { SystemStats } from './SystemStats'
import { useI18n, type Locale } from '@/lib/i18n'

interface BackendInfo {
  name: string
  url: string
  status: 'active' | 'inactive' | 'error'
}

export function SettingsView() {
  const { availableModels, selectedModel, setSelectedModel, locale = 'fr', setLocale } = useUIStore()
  const { t } = useI18n()
  
  const [isRefreshLoading, setIsRefreshLoading] = useState(false)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [mounted, setMounted] = useState(false)

  // Initialize on mount
  useEffect(() => {
    setMounted(true)
    setHasLoaded(true)
  }, [])

  // Backend status check
  const [backendInfo, setBackendInfo] = useState<BackendInfo[]>([
    { name: 'Ollama', url: LLM_CONFIG.ollamaUrl, status: 'inactive' as const },
    { name: 'LM Studio', url: LLM_CONFIG.lmstudioUrl, status: 'inactive' as const },
    { name: 'llama.cpp', url: LLM_CONFIG.llamacppUrl, status: 'inactive' as const },
    { name: 'Lemonade', url: LLM_CONFIG.lemonadeUrl, status: 'inactive' as const },
  ])

  // Test backend connectivity
  useEffect(() => {
    const checkBackends = async () => {
      const results = await Promise.all(
        backendInfo.map(async (backend) => {
          try {
            const response = await fetch(`${backend.url}/api/tags`, { signal: AbortSignal.timeout(2000) })
            if (response.ok) return { ...backend, status: 'active' as const }
          } catch {
            try {
              const response = await fetch(`${backend.url}/api/v1/models`, { signal: AbortSignal.timeout(2000) })
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

  const handleLocaleChange = (newLocale: Locale) => {
    setLocale(newLocale)
  }

  const modelCount = availableModels.length

  if (!mounted) return null

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="flex-1 p-4 overflow-y-auto"
    >
      {/* Header */}
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-white mb-1">
          {t.t.settings.title}
        </h2>
        <p className="text-xs text-slate-500">
          {t.t.settings.subtitle}
        </p>
      </div>

      {/* Grid Layout - 2 columns on md+, stack on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Section: Language */}
        <section className="bg-slate-800/50 rounded-xl p-4 border border-slate-800/60">
          <h3 className="text-xs font-semibold text-slate-400 mb-3 flex items-center gap-2">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5h12M9 3v2m1.048 9.5A18.023 18.023 0 016.412 9m6.088 9h7M11 21l5-10 5 10" />
            </svg>
            {t.t.settings.language}
          </h3>
          <select
            value={locale}
            onChange={(e) => handleLocaleChange(e.target.value as Locale)}
            className="w-full bg-slate-700/80 border border-slate-600 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500 appearance-none"
          >
            <option value="fr">🇫🇷 Français</option>
            <option value="en">🇬🇧 English</option>
          </select>
        </section>
        <section className="bg-slate-800/50 rounded-xl p-4 border border-slate-800/60">
          <h3 className="text-xs font-semibold text-slate-400 mb-3 flex items-center gap-2">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {t.t.settings.about}
          </h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white font-semibold">UI-Pro</p>
              <p className="text-xs text-slate-500">v1.0.0</p>
            </div>
            <span className="text-xs text-slate-500">{hasLoaded ? '✓' : '...'}</span>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            Ollama + Next.js
          </p>
        </section>

        {/* Section: Models - Full width */}
        <section className="md:col-span-2 bg-slate-800/50 rounded-xl p-4 border border-slate-800/60">
          <h3 className="text-xs font-semibold text-slate-400 mb-3 flex items-center gap-2">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            {t.t.settings.modelsSection}
          </h3>

          <div className="flex items-center gap-3 mb-3">
            <div className="flex-1">
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="w-full bg-slate-700/80 border border-slate-600 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500"
              >
                {availableModels.length === 0 ? (
                  <option value="">No models</option>
                ) : (
                  availableModels.map((model) => (
                    <option key={model} value={model}>{model}</option>
                  ))
                )}
              </select>
            </div>
            <button
              onClick={handleRefreshModels}
              disabled={isRefreshLoading}
              className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white text-xs px-3 py-2 rounded-lg transition-all"
            >
              {isRefreshLoading ? '⟳' : '↻'} {t.t.settings.refresh}
            </button>
          </div>
          <p className="text-xs text-slate-500">{modelCount} model{modelCount !== 1 ? 's' : ''} available</p>
        </section>

        {/* Section: Backend Connections - Full width */}
        <section className="md:col-span-2 bg-slate-800/50 rounded-xl border border-slate-800/60 overflow-hidden">
          <h3 className="text-xs font-semibold text-slate-400 p-3 border-b border-slate-700/50 flex items-center gap-2">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2m-2-4h.01M17 16h.01" />
            </svg>
            {t.t.settings.backendConnections}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-slate-700/30">
            {backendInfo.map((backend) => (
              <div key={backend.name} className="p-3 text-center">
                <p className="text-xs text-slate-400 mb-1">{backend.name}</p>
                <span className={`inline-flex items-center gap-1 text-xs ${backend.status === 'active' ? 'text-emerald-400' : 'text-slate-500'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${backend.status === 'active' ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                  {backend.status === 'active' ? t.t.settings.active : t.t.settings.inactive}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Section: System Stats - Full width */}
        <section className="md:col-span-2">
          <SystemStats />
        </section>
      </div>
    </motion.div>
  )
}
