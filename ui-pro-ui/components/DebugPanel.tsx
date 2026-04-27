// DebugPanel.tsx
// Role: Debug sidebar panel - displays agent execution status, model info, step progress, live logs

'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { translations, type Translations } from '@/lib/i18n'
import { useUIStore } from '@/lib/stores/uiStore'

interface AgentStep {
  id: string
  title: string
  detail?: string
  status: 'pending' | 'active' | 'done' | 'error'
}

interface DebugPanelProps {
  steps?: AgentStep[]
  isOpen: boolean
  onClose?: () => void
  onToggle?: () => void
  status?: 'idle' | 'running' | 'completed' | 'error'
  modelName?: string
  elapsedSeconds?: number
  tokenCount?: number
  connectionStatus?: string
  lastErrorMsg?: string
  currentStep?: number
  logs?: string[]
  onClearLogs?: () => void
  subscribeToStore?: boolean
  locale?: 'en' | 'fr'
}

export function DebugPanel({
  steps = [],
  isOpen,
  onClose,
  onToggle,
  status = 'idle',
  modelName = 'gemma4:latest',
  elapsedSeconds = 0,
  tokenCount: propTokenCount = 0,
  lastErrorMsg,
  currentStep = 0,
  logs = [],
  onClearLogs,
  subscribeToStore = true,
  locale = 'en',
}: DebugPanelProps) {
  const { locale: storeLocale = 'fr' } = useUIStore()
  const t: Translations = translations[storeLocale]
  
  const [localTokenCount, setLocalTokenCount] = useState(propTokenCount)
  const logsEndRef = useRef<HTMLDivElement>(null)

  // FIX: Force sync when prop changes (handles React.memo parent issues)
  useEffect(() => {
    if (propTokenCount !== localTokenCount) {
      setLocalTokenCount(propTokenCount)
    }
  }, [propTokenCount, localTokenCount])

  // Derived state optimization
  const completed = useMemo(
    () => steps.filter((s) => s.status === 'done').length,
    [steps]
  )

  const progress = useMemo(() => {
    return steps.length ? Math.round((completed / steps.length) * 100) : 0
  }, [steps.length, completed])

  // Use active step index as the source of truth for current step (consistent with StepProgress)
  const activeStepNumber = useMemo(() => {
    const activeIdx = steps.findIndex((s) => s.status === 'active')
    return activeIdx !== -1 ? activeIdx + 1 : steps.length > 0 ? Math.max(1, currentStep + 1) : 1
  }, [steps, currentStep])

  useEffect(() => {
    if (!isOpen) return
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs.length, isOpen])

  const closeFn = useCallback(() => {
    onClose?.() ?? onToggle?.()
  }, [onClose, onToggle])

  if (!isOpen) {
    return (
      <button
        onClick={closeFn}
        className="fixed right-4 top-4 bg-slate-800 border border-slate-700 text-slate-400 px-3 py-2 rounded-lg text-xs hover:bg-slate-700 z-50"
      >
        🔧 Debug {status === 'running' && '●'}
      </button>
    )
  }

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      transition={{ type: 'spring', damping: 28, stiffness: 400 }}
      className="w-80 border-l border-slate-800/60 bg-[#0a0a0f] flex flex-col h-full shadow-2xl"
    >
      {/* HEADER */}
      <div className="bg-slate-900/50 px-4 py-3 border-b border-slate-800/60 flex items-center justify-between">
        <span className="text-sm font-semibold">🔧 {t.debug?.title || 'Debug Panel'}</span>
        <button
          onClick={closeFn}
          className="text-slate-400 hover:text-white text-xs"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* STATUS */}
        <div className="p-4 space-y-3 border-b border-slate-800/60">
          <Row label={t.debug?.status || 'Status'} value={status.toUpperCase()} />
          <Row label={t.debug?.model || 'Model'} value={modelName} color="violet" />
          <Row label={t.debug?.backend || 'Backend'} value="🦙 Ollama" />
          <Row label={t.debug?.elapsed || 'Elapsed'} value={`${elapsedSeconds}s`} />
          <Row label={t.debug?.tokens || 'Tokens'} value={localTokenCount} color="violet" bold />
        </div>

        {/* PROGRESS - only show when agent is actively running (not idle/error) */}
        {steps.length > 0 && status === 'running' && (
          <div className="p-4 border-b border-slate-800/60">
            <div className="flex justify-between text-xs mb-2">
              <span>{typeof t.steps.stepLabel === 'function' ? t.steps.stepLabel(activeStepNumber, steps.length) : `Step ${activeStepNumber}/${steps.length}`}</span>
              <span>{elapsedSeconds}s</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-violet-500"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* STEPS */}
        <div className="p-4 border-b border-slate-800/60">
          <div className="text-xs text-slate-500 mb-3">{t.debug?.agentExecution || 'Agent Execution'}</div>
          {steps.map((step, i) => (
            <div key={`${step.id}-${i}`} className="flex gap-3 text-sm mb-2">
              <div className="w-5 h-5 flex items-center justify-center rounded-full text-xs bg-slate-800">
                {step.status === 'done'
                  ? '✓'
                  : step.status === 'active'
                  ? '●'
                  : Math.max(1, activeStepNumber)}
              </div>
              <div>
                <div
                  className={step.status === 'active' ? 'text-white' : 'text-slate-400'}
                >
                  {step.title}
                </div>
                {step.detail && (
                  <div className="text-xs text-slate-500">{step.detail}</div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* LOGS */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="px-4 py-2 border-b border-slate-800 flex justify-between">
            <span className="text-xs text-slate-500">Live Logs</span>
            <button
              onClick={onClearLogs}
              className="text-[10px] text-slate-500"
            >
              Clear
            </button>
          </div>
          <div className="flex-1 p-4 font-mono text-[10px] overflow-y-auto">
            {logs.length === 0 ? (
              <span className="text-slate-600 italic">Waiting...</span>
            ) : (
              logs.map((l, i) => <div key={`log-${i}-${l.slice(0, 10)}`}>{l}</div>)
            )}
            <div ref={logsEndRef} />
          </div>
        </div>
      </div>

      {/* ERROR - only show when status is error */}
      {lastErrorMsg && status === 'error' ? (
        <div className="p-3 text-xs text-red-400 border-t border-red-900/30">
          ⚠ {lastErrorMsg.split('\n')[0]}
        </div>
      ) : null}
    </motion.div>
  )
}

// =====================
// SMALL UI HELPER
// =====================
function Row({
  label,
  value,
  color,
  bold,
}: {
  label: string
  value: any
  color?: 'violet'
  bold?: boolean
}) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-slate-500">{label}</span>
      <span
        className={`font-mono ${
          color === 'violet' ? 'text-violet-400' : 'text-slate-300'
        } ${bold ? 'font-bold' : ''}`}
      >
        {value}
      </span>
    </div>
  )
}
