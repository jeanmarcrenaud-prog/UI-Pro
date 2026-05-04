// components/settings/SettingsView.tsx
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
  const { availableModels, selectedModel, setSelectedModel } = useUIStore()
  const { t, locale, setLocale } = useI18n()

  const [isRefreshLoading, setIsRefreshLoading] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const [modelDescription, setModelDescription] = useState<string | null>(null)
  const [isLoadingDescription, setIsLoadingDescription] = useState(false)

  const [backendInfo, setBackendInfo] = useState<BackendInfo[]>([
    { name: 'Ollama', url: LLM_CONFIG.ollamaUrl, status: 'inactive' },
    { name: 'LM Studio', url: LLM_CONFIG.lmstudioUrl, status: 'inactive' },
    { name: 'llama.cpp', url: LLM_CONFIG.llamacppUrl, status: 'inactive' },
    { name: 'Lemonade', url: LLM_CONFIG.lemonadeUrl, status: 'inactive' },
  ])

  // Check backend connectivity once on mount
  useEffect(() => {
    const checkBackends = async () => {
      const results = await Promise.all(
        backendInfo.map(async (backend): Promise<BackendInfo> => {
          const endpoints = [`${backend.url}/api/tags`, `${backend.url}/api/v1/models`]

          for (const endpoint of endpoints) {
            try {
              const controller = new AbortController()
              const timeoutId = setTimeout(() => controller.abort(), 2500)

              const res = await fetch(endpoint, { signal: controller.signal })
              clearTimeout(timeoutId)

              if (res.ok) {
                return { ...backend, status: 'active' }
              }
            } catch {
              // Try next endpoint
            }
          }
          return backend // remains 'inactive'
        })
      )
      setBackendInfo(results)
    }

    checkBackends()
  }, []) // Empty dependency array = run once

  // Fetch model description when selected model changes
  useEffect(() => {
    const fetchDescription = async () => {
      if (!selectedModel || selectedModel === 'default') {
        setModelDescription(null)
        return
      }
      
      setIsLoadingDescription(true)
      try {
        // Try GitHub API first
        const res = await fetch(`https://api.github.com/search/repositories?q=${encodeURIComponent(selectedModel)}+in:name&per_page=1`, {
          headers: { Accept: 'application/vnd.github.v3+json' }
        })
        if (res.ok) {
          const data = await res.json()
          if (data.items?.[0]?.description) {
            setModelDescription(data.items[0].description)
            setIsLoadingDescription(false)
            return
          }
        }
        // Try Ollama API as fallback
        const ollamaRes = await fetch('http://localhost:11434/api/tags')
        if (ollamaRes.ok) {
          const ollamaData = await ollamaRes.json()
          const model = ollamaData.models?.find((m: any) => m.name === selectedModel)
          if (model?.details?.description) {
            setModelDescription(model.details.description)
            setIsLoadingDescription(false)
            return
          }
        }
        setModelDescription('Large language model from Ollama')
      } catch {
        setModelDescription('Large language model')
      } finally {
        setIsLoadingDescription(false)
      }
    }
    
    fetchDescription()
  }, [selectedModel])

  const handleRefreshModels = async () => {
    setIsRefreshLoading(true)
    setRefreshError(null)

    try {
      await modelDiscovery.discover()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to refresh models'
      setRefreshError(message)
      console.error('Model discovery failed:', err)
    } finally {
      setIsRefreshLoading(false)
    }
  }

  const handleLocaleChange = (newLocale: Locale) => {
    setLocale(newLocale)
  }

  const modelCount = availableModels.length

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="flex-1 p-6 overflow-y-auto"
    >
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-white tracking-tight">
          {t.settings.title}
        </h2>
        <p className="text-slate-400 mt-1 text-[15px]">
          {t.settings.subtitle}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Language */}
        <section className="bg-slate-800/70 rounded-2xl p-6 border border-slate-700">
          <h3 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
            🌐 {t.settings.language}
          </h3>
          <select
            value={locale}
            onChange={(e) => handleLocaleChange(e.target.value as Locale)}
            className="w-full bg-slate-900 border border-slate-600 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
          >
            <option value="fr">🇫🇷 Français</option>
            <option value="en">🇬🇧 English</option>
          </select>
        </section>

        {/* About */}
        <section className="bg-slate-800/70 rounded-2xl p-6 border border-slate-700">
          <h3 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
            ℹ️ {t.settings.about}
          </h3>
          <a 
            href="https://github.com/jeanmarcrenaud-prog/UI-Pro" 
            target="_blank"
            rel="noopener noreferrer"
            className="flex justify-between items-start hover:bg-slate-700/50 p-2 -m-2 rounded-xl transition-colors cursor-pointer group"
          >
            <div>
              <p className="text-lg font-semibold text-white group-hover:text-violet-300 transition-colors">UI-Pro</p>
              <p className="text-xs text-slate-500 mt-0.5">Version 1.0.0 • Built with Next.js + Ollama</p>
            </div>
            <span className="text-emerald-400 text-2xl">✓</span>
          </a>
        </section>

        {/* Models Section */}
        <section className="lg:col-span-2 bg-slate-800/70 rounded-2xl p-6 border border-slate-700">
          <h3 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
            🤖 {t.settings.modelsSection}
          </h3>

          <div className="flex flex-col sm:flex-row gap-3">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-600 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500"
            >
              {modelCount === 0 ? (
                <option value="">Aucun modèle disponible</option>
              ) : (
                availableModels.map((model) => (
                  <option key={`${model.provider}-${model.name}`} value={model.name}>
                    {model.name} [{model.provider}]
                  </option>
                ))
              )}
            </select>

            <button
              onClick={handleRefreshModels}
              disabled={isRefreshLoading}
              className="px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:bg-violet-800/70 disabled:cursor-wait text-white text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2 whitespace-nowrap min-w-[120px]"
            >
              {isRefreshLoading ? (
                <>⟳ {t.settings.refreshing}</>
              ) : (
                <>↻ {t.settings.refresh}</>
              )}
            </button>
          </div>

          {/* Model Description */}
          {selectedModel && selectedModel !== 'default' && (
            <div className="mt-4 p-4 bg-slate-900/50 rounded-xl border border-slate-700/50">
              {isLoadingDescription ? (
                <div className="flex items-center gap-2 text-slate-500 text-sm">
                  <span className="animate-pulse">Loading description...</span>
                </div>
              ) : modelDescription ? (
                <p className="text-sm text-slate-300 leading-relaxed">{modelDescription}</p>
              ) : (
                <p className="text-sm text-slate-500">Large language model</p>
              )}
            </div>
          )}

          {refreshError && (
            <p className="mt-3 text-sm text-red-400 bg-red-950/50 border border-red-900/50 rounded-lg px-4 py-2">
              ⚠️ {refreshError}
            </p>
          )}

          <p className="mt-4 text-xs text-slate-500">
            {modelCount} modèle{modelCount !== 1 ? 's' : ''} disponible{modelCount !== 1 ? 's' : ''}
          </p>
        </section>

        {/* Backend Connections */}
        <section className="lg:col-span-2 bg-slate-800/70 rounded-2xl border border-slate-700 overflow-hidden">
          <h3 className="text-sm font-medium text-slate-300 p-6 border-b border-slate-700 flex items-center gap-2">
            🔌 {t.settings.backendConnections}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4">
            {backendInfo.map((backend) => (
              <div key={backend.name} className="p-6 text-center border-b border-slate-700 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0">
                <p className="font-medium text-white mb-2">{backend.name}</p>
                <div className={`inline-flex items-center gap-2 text-sm ${backend.status === 'active' ? 'text-emerald-400' : 'text-slate-500'}`}>
                  <div className={`w-2.5 h-2.5 rounded-full ${backend.status === 'active' ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                  {backend.status === 'active' ? t.settings.active : t.settings.inactive}
                </div>
                <p className="text-[10px] text-slate-600 mt-3 truncate font-mono">{backend.url}</p>
              </div>
            ))}
          </div>
        </section>

        {/* System Stats */}
        <section className="lg:col-span-2 pt-2">
          <SystemStats />
        </section>
      </div>
    </motion.div>
  )
}