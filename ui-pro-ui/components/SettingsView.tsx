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
  responseTime?: number // Response time in ms
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
        const endpoints = [`${backend.url}/api/tags`, `${backend.url}/api/v1/models`]
        let status: BackendInfo['status'] = 'inactive'
        let responseTime: number | undefined

        for (const endpoint of endpoints) {
          try {
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 2500)

            const startTime = Date.now()
            const res = await fetch(endpoint, { signal: controller.signal })
            responseTime = Date.now() - startTime
            clearTimeout(timeoutId)

            if (res.ok) {
              status = 'active'
              break
            }
          } catch (err) {
            if (err instanceof Error && err.name !== 'AbortError') {
              status = 'error'
            }
          }
        }
        return { ...backend, status, responseTime }
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

          {/* Model Search */}
          <input
            type="text"
            placeholder={t.settings.searchModels || 'Search models...'}
            value={modelSearch}
            onChange={(e) => setModelSearch(e.target.value)}
            className="w-full bg-slate-900 border border-slate-600 rounded-xl px-4 py-2 mb-3 text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
          />

          <div className="flex flex-col sm:flex-row gap-3">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-600 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-violet-500"
            >
              {filteredModels.length === 0 ? (
                <option value="">Aucun modèle disponible</option>
              ) : (
                filteredModels.map((model) => {
                  // Build display string with metadata
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
              className="px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:bg-violet-800/70 disabled:cursor-wait text-white text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2 whitespace-nowrap min-w-[120px]"
            >
              {isRefreshLoading ? (
                <span>⟳ {t.settings.refreshing}</span>
              ) : (
                <span>↻ {t.settings.refresh}</span>
              )}
            </button>
          </div>

          {/* Model Description */}
          {selectedModel && selectedModel !== 'default' && (
            <div className="mt-4 p-4 bg-slate-900/50 rounded-xl border border-slate-700/50">
              {isLoadingDescription ? (
                <p className="text-sm text-slate-400">⏳ {t.settings.loadingDescription || 'Loading description...'}</p>
              ) : selectedModelInfo ? (
                <div className="space-y-2">
                  {/* Main info */}
                  <div className="flex flex-wrap gap-2 mb-3">
                    {selectedModelInfo.parameterSize && (
                      <span className="px-2 py-1 bg-violet-600/20 text-violet-300 text-xs rounded">
                        {selectedModelInfo.parameterSize}
                      </span>
                    )}
                    {selectedModelInfo.quantization && (
                      <span className="px-2 py-1 bg-blue-600/20 text-blue-300 text-xs rounded">
                        {selectedModelInfo.quantization}
                      </span>
                    )}
                    {selectedModelInfo.sizeGb && (
                      <span className="px-2 py-1 bg-emerald-600/20 text-emerald-300 text-xs rounded">
                        {selectedModelInfo.sizeGb} GB
                      </span>
                    )}
                    {selectedModelInfo.maxContext && (
                      <span className="px-2 py-1 bg-amber-600/20 text-amber-300 text-xs rounded">
                        {selectedModelInfo.maxContext.toLocaleString()} ctx
                      </span>
                    )}
                    {selectedModelInfo.speedTier && (
                      <span className={`px-2 py-1 text-xs rounded ${
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
                        <span key={cap} className="px-2 py-0.5 bg-slate-700 text-slate-400 text-xs rounded capitalize">
                          {cap}
                        </span>
                      ))}
                    </div>
                  )}
                  
                  {/* Backend */}
                  <div className="pt-2 border-t border-slate-700/50">
                    <span className="text-xs text-slate-500">
                      Backend: <span className="text-slate-400">{selectedModelInfo.provider}</span>
                    </span>
                  </div>
                </div>
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
          <div className="p-6 border-b border-slate-700 flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-300 flex items-center gap-2">
              🔌 {t.settings.backendConnections}
            </h3>
            <button
              onClick={checkBackends}
              aria-label={t.settings.testBackendsAria || 'Test backend connectivity'}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-sm text-slate-300 rounded-lg transition-colors flex items-center gap-2"
            >
              ✅ {t.settings.testBackends || 'Test'}
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4">
            {backendInfo.map((backend) => (
              <div key={backend.name} aria-label={`Backend ${backend.name} is ${backend.status}`} className="p-6 text-center border-b border-slate-700 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0">
                <p className="font-medium text-white mb-2">{backend.name}</p>
                <div className={`inline-flex items-center gap-2 text-sm ${
                  backend.status === 'active' ? 'text-emerald-400' :
                  backend.status === 'error' ? 'text-red-400' :
                  'text-slate-500'
                }`}>
                  <div className={`w-2.5 h-2.5 rounded-full ${
                    backend.status === 'active' ? 'bg-emerald-400' :
                    backend.status === 'error' ? 'bg-red-400' :
                    'bg-slate-600'
                  }`} />
                  {backend.status === 'active' ? t.settings.active :
                   backend.status === 'error' ? `⚠️ ${t.settings.error || 'Error'}` :
                   t.settings.inactive}
                </div>
                {backend.responseTime && (
                  <p className="text-[10px] text-slate-500 mt-1">{backend.responseTime}ms</p>
                )}
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