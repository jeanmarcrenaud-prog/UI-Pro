// ModelSelector.tsx
'use client'

import { useModelDiscovery } from './hooks/useModelDiscovery'
import { useModelDescription } from './hooks/useModelDescription'
import { useI18n } from '@/lib/i18n'

interface ModelSelectorProps {
  className?: string
}

export function ModelSelector({ className = '' }: ModelSelectorProps) {
  const { t } = useI18n()
  const {
    filteredModels,
    selectedModel,
    search,
    isRefreshing,
    error,
    setSearch,
    handleRefresh,
    handleSelectModel,
    selectedModelInfo,
  } = useModelDiscovery()

  const { description, isLoading: isLoadingDescription } = useModelDescription(selectedModel)

  return (
    <section className={`glass-panel rounded-xl p-4 transition-all duration-200 hover:border-[var(--accent)]/30 ${className}`}>
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        🤖 {t.settings.modelsSection}
      </h3>

      {/* Model Search - Compact */}
      <input
        type="text"
        placeholder={t.settings.searchModels || 'Search models...'}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-2 mb-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-violet-500 transition-colors"
      />

      <div className="flex flex-col sm:flex-row gap-3">
        <select
          value={selectedModel || ''}
          onChange={(e) => handleSelectModel(e.target.value)}
          className="flex-1 bg-[#172033] border border-slate-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-violet-500"
        >
          {filteredModels.length === 0 ? (
            <option value="">Aucun modèle disponible</option>
          ) : (
            filteredModels.map((model) => {
              const prefix = model.isLoaded ? '\u25CF ' : '\u25CB '
              const parts = [prefix + model.name]
              if (model.sizeGb) parts.push(`${model.sizeGb}GB`)
              if (model.speedTier && model.speedTier !== 'fast') parts.push(model.speedTier)
              if (model.isLoaded) {
                const vram = model.sizeVramGb ? `${model.sizeVramGb}GB VRAM` : 'in VRAM'
                parts.push(vram)
              }
              parts.push(model.provider)

              return (
                <option key={`${model.provider}-${model.id}`} value={model.id}>
                  {parts.join(' \u2022 ')}
                </option>
              )
            })
          )}
        </select>

        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="px-4 py-2.5 bg-violet-600 hover:bg-violet-700 disabled:bg-violet-800/70 disabled:cursor-wait text-white text-sm font-medium rounded-lg transition-all flex items-center justify-center gap-2 whitespace-nowrap"
        >
          {isRefreshing ? (
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
                {/* Loaded in VRAM badge */}
                {selectedModelInfo.isLoaded && (
                  <span className="px-2 py-0.5 bg-emerald-600/20 text-emerald-300 text-[10px] rounded inline-flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_4px_rgba(52,211,153,0.5)]" />
                    {selectedModelInfo.sizeVramGb ? `${selectedModelInfo.sizeVramGb}GB VRAM` : 'in VRAM'}
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
            <p className="text-xs text-slate-500">{description || t.settings.modelFallbackDesc}</p>
          )}
        </div>
      )}

      {error && (
        <p className="mt-3 text-xs text-red-400 bg-red-950/50 border border-red-900/30 rounded-lg px-3 py-2">
          ⚠️ {error}
        </p>
      )}
    </section>
  )
}