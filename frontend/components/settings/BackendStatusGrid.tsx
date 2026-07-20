// BackendStatusGrid.tsx
'use client'

import { useBackendStatus } from './hooks/useBackendStatus'
import { useI18n } from '@/lib/i18n'
import type { BackendInfo } from './types'

interface BackendStatusGridProps {
  className?: string
}

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

export function BackendStatusGrid({ className = '' }: BackendStatusGridProps) {
  const { t } = useI18n()
  const { backendInfo, checkBackends, isChecking } = useBackendStatus()

  return (
    <section className={className}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[11px] uppercase tracking-wider text-slate-400 flex items-center gap-2">
          🔌 {t.settings.backendConnections}
        </h3>
        <button
          onClick={checkBackends}
          disabled={isChecking}
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
            className={`glass-panel rounded-xl p-4 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)] ${
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
                <span className="text-slate-500">{t.settings.metricsLatency}</span>
                <p className="text-slate-300 font-mono">
                  {backend.responseTime ? `${backend.responseTime}ms` : '—'}
                </p>
              </div>
              <div>
                <span className="text-slate-500">{t.settings.metricsModels}</span>
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
  )
}