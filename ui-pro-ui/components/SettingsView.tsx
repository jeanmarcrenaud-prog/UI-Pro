// components/settings/SettingsView.tsx
'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
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
  responseTime?: number
  modelCount?: number
  lastChecked?: number
}

export function SettingsView() {
  const { availableModels, selectedModel, setSelectedModel } = useUIStore()
  const { t, locale, setLocale } = useI18n()

  const [isRefreshLoading, setIsRefreshLoading] = useState(false)
  const [refreshError, setRefreshError] = useState<string | null>(null)
  const [modelDescription, setModelDescription] = useState<string | null>(null)
  const [isLoadingDescription, setIsLoadingDescription] = useState(false)
  
  // Model search filter
  const [modelSearch, setModelSearch] = useState('')

  // Get selected model's metadata
  const selectedModelInfo = availableModels.find(m => m.name === selectedModel)

  // Memoized filtered models based on search
  const filteredModels = useMemo(() =>
    availableModels.filter(model =>
      model.name.toLowerCase().includes(modelSearch.toLowerCase()) ||
      model.provider.toLowerCase().includes(modelSearch.toLowerCase())
    ),
    [availableModels, modelSearch]
  )

  const [backendInfo, setBackendInfo] = useState<BackendInfo[]>([
    { name: 'Ollama', url: LLM_CONFIG.ollamaUrl, status: 'inactive' },
    { name: 'LM Studio', url: LLM_CONFIG.lmstudioUrl, status: 'inactive' },
    { name: 'llama.cpp', url: LLM_CONFIG.llamacppUrl, status: 'inactive' },
    { name: 'Lemonade', url: LLM_CONFIG.lemonadeUrl, status: 'inactive' },
  ])

  // Memoized backend check function
  const checkBackends = useCallback(async () => {
    const results = await Promise.all(
      backendInfo.map(async (backend): Promise<BackendInfo> => {
        const endpoints = [
          { url: `${backend.url}/api/tags`, v1: false },
          { url: `${backend.url}/api/v1/models`, v1: true }
        ]
        let status: BackendInfo['status'] = 'inactive'
        let responseTime: number | undefined
        let modelCount = 0

        for (const endpoint of endpoints) {
          try {
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 2500)

            const startTime = Date.now()
            const res = await fetch(endpoint.url, { signal: controller.signal })
            responseTime = Date.now() - startTime
            clearTimeout(timeoutId)

            if (res.ok) {
              status = 'active'
              try {
                const data = await res.json()
                modelCount = data.models?.length || 0
              } catch {}
              break
            }
          } catch (err) {
            if (err instanceof Error && err.name !== 'AbortError') {
              status = 'error'
            }
          }
        }
        return { ...backend, status, responseTime, modelCount, lastChecked: Date.now() }
      })
    )
    setBackendInfo(results)
  }, [backendInfo])

  // Check backend connectivity once on mount
  useEffect(() => {
    checkBackends()
  }, [checkBackends])

  // Memoized fetch description function
  const fetchDescription = useCallback(async () => {
    if (!selectedModel || selectedModel === 'default') {
      setModelDescription(null)
      return
    }
    
    setIsLoadingDescription(true)
    try {
      // Try GitHub API first with timeout
      const githubController = new AbortController()
      const githubTimeout = setTimeout(() => githubController.abort(), 3000)
      const githubRes = await fetch(
        `https://api.github.com/search/repositories?q=${encodeURIComponent(selectedModel)}+in:name&per_page=1`,
        { signal: githubController.signal, headers: { Accept: 'application/vnd.github.v3+json' } }
      )
      clearTimeout(githubTimeout)

      if (githubRes.ok) {
        const data = await githubRes.json()
        if (data.items?.[0]?.description) {
          setModelDescription(data.items[0].description)
          setIsLoadingDescription(false)
          return
        }
      } else if (!githubRes.ok && githubRes.status !== 429) {
        console.warn(`GitHub API error: ${githubRes.status}`)
      }

      // Try Ollama API as fallback with timeout
      const ollamaController = new AbortController()
      const ollamaTimeout = setTimeout(() => ollamaController.abort(), 3000)
      const ollamaRes = await fetch(`${LLM_CONFIG.ollamaUrl}/api/tags`, {
        signal: ollamaController.signal
      })
      clearTimeout(ollamaTimeout)

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
    } catch (err) {
      console.warn('Failed to fetch model description:', err)
      setModelDescription('Large language model')
    } finally {
      setIsLoadingDescription(false)
    }
  }, [selectedModel])

  // Fetch model description when selected model changes
  useEffect(() => {
    fetchDescription()
  }, [fetchDescription])

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

  // Helper for status color
  const getStatusColor = (status: BackendInfo['status']) => {
    switch (status) {
      case 'active': return 'text-emerald-400'
      case 'error': return 'text-amber-400'
      default: return 'text-slate-500'
    }
  }

  const getStatusDot = (status: BackendInfo['status']) => {
    switch (status) {
      case 'active': return 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]'
      case 'error': return 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]'
      default: return 'bg-slate-600'
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="flex-1 p-4 sm:p-6 overflow-y-auto"
    >
      {/* Header - Compact */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white tracking-tight">
          {t.settings.title}
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          {t.settings.subtitle}
        </p>
      </div>

      {/* Dashboard Grid - 3 columns on large screens */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        
        {/* Language - Compact Card */}
        <section className="bg-[#0f172a] rounded-xl p-4 border border-slate-700/50 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
          <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
            🌐 {t.settings.language}
          </h3>
          <select
            value={locale}
            onChange={(e) => handleLocaleChange(e.target.value as Locale)}
            className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition-colors"
          >
            <option value="fr">🇫🇷 Français</option>
            <option value="en">🇬🇧 English</option>
          </select>
        </section>

        {/* About - Compact Card */}
        <section className="bg-[#0f172a] rounded-xl p-4 border border-slate-700/50 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
          <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
            ℹ️ {t.settings.about}
          </h3>
          <a 
            href="https://github.com/jeanmarcrenaud-prog/UI-Pro" 
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between p-2 -mx-2 rounded-lg hover:bg-slate-800/50 transition-colors group"
          >
            <div>
              <p className="text-sm font-semibold text-white group-hover:text-violet-300 transition-colors">UI-Pro</p>
              <p className="text-[11px] text-slate-500 mt-0.5">v1.0.0 • Next.js + Ollama</p>
            </div>
            <span className="text-emerald-400 text-lg">✓</span>
          </a>
        </section>

        {/* Model Count - Compact Card */}
        <section className="bg-[#0f172a] rounded-xl p-4 border border-slate-700/50">
          <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
            📊 Modèles
          </h3>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white">{modelCount}</span>
            <span className="text-xs text-slate-500">disponibles</span>
          </div>
        </section>

        {/* Models Section - Full Width */}
        <section className="md:col-span-2 lg:col-span-3 bg-[#0f172a] rounded-xl p-4 border border-slate-700/50 hover:border-violet-500/30 transition-all duration-200">
          <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
            🤖 {t.settings.modelsSection}
          </h3>

          {/* Model Search - Compact */}
          <input
            type="text"
            placeholder={t.settings.searchModels || 'Search models...'}
            value={modelSearch}
            onChange={(e) => setModelSearch(e.target.value)}
            className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-2 mb-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-colors"
          />

          <div className="flex flex-col sm:flex-row gap-3">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="flex-1 bg-[#172033] border border-slate-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-violet-500"
            >
              {filteredModels.length === 0 ? (
                <option value="">Aucun modèle disponible</option>
              ) : (
                filteredModels.map((model) => {
                  const parts = [model.name]
                  if (model.sizeGb) parts.push(`${model.sizeGb}GB`)
                  if (model.speedTier && model.speedTier !== 'fast') parts.push(model.speedTier)
                  parts.push(model.provider)
                  
                  return (
                    <option key={`${model.provider}-${model.name}`} value={model.name}>
                      {parts.join(' • ')}
                    </option>
                  )
                })
              )}
            </select>

            <button
              onClick={handleRefreshModels}
              disabled={isRefreshLoading}
              className="px-4 py-2.5 bg-violet-600 hover:bg-violet-700 disabled:bg-violet-800/70 disabled:cursor-wait text-white text-sm font-medium rounded-lg transition-all flex items-center justify-center gap-2 whitespace-nowrap"
            >
              {isRefreshLoading ? (
                <span>⟳ {t.settings.refreshing}</span>
              ) : (
                <span>↻ {t.settings.refresh}</span>
              )}
            </button>
          </div>

          {/* Model Description - Compact */}
          {selectedModel && selectedModel !== 'default' && (
            <div className="mt-3 p-3 bg-[#172033]/50 rounded-lg border border-slate-700/30">
              {isLoadingDescription ? (
                <p className="text-xs text-slate-400">⏳ {t.settings.loadingDescription || 'Loading...'}</p>
              ) : selectedModelInfo ? (
                <div className="space-y-2">
                  {/* Tags */}
                  <div className="flex flex-wrap gap-1.5">
                    {selectedModelInfo.parameterSize && (
                      <span className="px-2 py-0.5 bg-violet-600/20 text-violet-300 text-[10px] rounded">
                        {selectedModelInfo.parameterSize}
                      </span>
                    )}
                    {selectedModelInfo.quantization && (
                      <span className="px-2 py-0.5 bg-blue-600/20 text-blue-300 text-[10px] rounded">
                        {selectedModelInfo.quantization}
                      </span>
                    )}
                    {selectedModelInfo.sizeGb && (
                      <span className="px-2 py-0.5 bg-emerald-600/20 text-emerald-300 text-[10px] rounded">
                        {selectedModelInfo.sizeGb} GB
                      </span>
                    )}
                    {selectedModelInfo.maxContext && (
                      <span className="px-2 py-0.5 bg-amber-600/20 text-amber-300 text-[10px] rounded">
                        {selectedModelInfo.maxContext.toLocaleString()} ctx
                      </span>
                    )}
                    {selectedModelInfo.speedTier && (
                      <span className={`px-2 py-0.5 text-[10px] rounded ${
                        selectedModelInfo.speedTier === 'very_fast' ? 'bg-green-600/20 text-green-300' :
                        selectedModelInfo.speedTier === 'fast' ? 'bg-lime-600/20 text-lime-300' :
                        selectedModelInfo.speedTier === 'medium' ? 'bg-yellow-600/20 text-yellow-300' :
                        'bg-orange-600/20 text-orange-300'
                      }`}>
                        {selectedModelInfo.speedTier}
                      </span>
                    )}
                  </div>
                  
                  {/* Capabilities */}
                  {selectedModelInfo.capabilities && selectedModelInfo.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {selectedModelInfo.capabilities.map(cap => (
                        <span key={cap} className="px-2 py-0.5 bg-slate-700/50 text-slate-400 text-[10px] rounded capitalize">
                          {cap}
                        </span>
                      ))}
                    </div>
                  )}
                  
                  {/* Backend */}
                  <div className="pt-1.5 border-t border-slate-700/30">
                    <span className="text-[10px] text-slate-500">
                      Backend: <span className="text-slate-400">{selectedModelInfo.provider}</span>
                    </span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-500">Large language model</p>
              )}
            </div>
          )}

          {refreshError && (
            <p className="mt-3 text-xs text-red-400 bg-red-950/50 border border-red-900/30 rounded-lg px-3 py-2">
              ⚠️ {refreshError}
            </p>
          )}
        </section>

        {/* Backend Connections - Full Width Live Cards */}
        <section className="md:col-span-2 lg:col-span-3">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[11px] uppercase tracking-wider text-slate-400 flex items-center gap-2">
              🔌 {t.settings.backendConnections}
            </h3>
            <button
              onClick={checkBackends}
              aria-label={t.settings.testBackendsAria || 'Test backend connectivity'}
              className="px-3 py-1.5 bg-slate-700/50 hover:bg-slate-600/50 text-xs text-slate-300 rounded-lg transition-colors flex items-center gap-1.5"
            >
              ✅ {t.settings.testBackends || 'Test'}
            </button>
          </div>
          
          {/* Live Backend Cards Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {backendInfo.map((backend) => (
              <div 
                key={backend.name} 
                className={`bg-[#0f172a] rounded-xl p-4 border transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)] ${
                  backend.status === 'active' 
                    ? 'border-emerald-500/30 hover:border-emerald-400/50' 
                    : backend.status === 'error'
                    ? 'border-amber-500/30 hover:border-amber-400/50'
                    : 'border-slate-700/50 hover:border-slate-600/50'
                }`}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-medium text-white">{backend.name}</p>
                  <div className={`w-2 h-2 rounded-full ${getStatusDot(backend.status)}`} />
                </div>

                {/* Status */}
                <div className={`text-xs mb-3 ${getStatusColor(backend.status)}`}>
                  {backend.status === 'active' ? t.settings.active :
                   backend.status === 'error' ? `⚠️ ${t.settings.error || 'Error'}` :
                   t.settings.inactive}
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  <div>
                    <span className="text-slate-500">Latence</span>
                    <p className="text-slate-300 font-mono">
                      {backend.responseTime ? `${backend.responseTime}ms` : '—'}
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-500">Modèles</span>
                    <p className="text-cyan-400 font-mono">
                      {backend.modelCount ?? '—'}
                    </p>
                  </div>
                </div>

                {/* URL - Truncated */}
                <p className="text-[9px] text-slate-600 mt-3 truncate font-mono">{backend.url}</p>
              </div>
            ))}
          </div>
        </section>

        {/* System Stats - Full Width */}
        <section className="md:col-span-2 lg:col-span-3 pt-2">
          <SystemStats />
        </section>
      </div>
    </motion.div>
  )
}