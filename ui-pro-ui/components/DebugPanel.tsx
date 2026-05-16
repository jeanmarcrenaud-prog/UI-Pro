// DebugPanel.tsx
// Role: Debug sidebar panel - displays agent execution status, model info, step progress, live logs

'use client'

import { useCallback, useEffect, useMemo, useRef } from 'react'
import { motion } from 'framer-motion'
import { useI18n } from '@/lib/i18n'
import { VirtualizedLogs } from '@/components/VirtualizedLogs'
import type { AgentStep } from '@/lib/types'

interface DebugPanelProps {
  steps?: AgentStep[]
  isOpen: boolean
  onClose?: () => void
  onToggle?: () => void
  status?: 'idle' | 'running' | 'completed' | 'error'
  modelName?: string
  backend?: string
  elapsedSeconds?: number
  tokenCount?: number
  connectionStatus?: string
  lastErrorMsg?: string
  logs?: string[]
  onClearLogs?: () => void
  currentCode?: string
}

export function DebugPanel({
  steps = [],
  isOpen,
  onClose,
  onToggle,
  status = 'idle',
  modelName = 'gemma4:latest',
  backend = 'ollama',
  elapsedSeconds = 0,
  tokenCount = 0,
  lastErrorMsg,
  logs = [],
  onClearLogs,
  currentCode = '',
}: DebugPanelProps) {
  const { t } = useI18n()
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Derived values
  const completed = useMemo(
    () => steps.filter((s) => s.status === 'done').length,
    [steps]
  )

  const progress = useMemo(() => {
    return steps.length ? Math.round((completed / steps.length) * 100) : 0
  }, [steps.length, completed])

  const activeStepIndex = useMemo(() => {
    return steps.findIndex((s) => s.status === 'active')
  }, [steps])

  const activeStepNumber = activeStepIndex !== -1
    ? activeStepIndex + 1
    : steps.length > 0
      ? 1
      : 0

  // Backend display name
  const backendDisplay = useMemo(() => {
    switch (backend) {
      case 'ollama': return '🦙 Ollama'
      case 'lmstudio': return '🖥️ LM Studio'
      case 'lemonade': return '🍋 Lemonade'
      default: return backend
    }
  }, [backend])

  // Auto-scroll logs
  useEffect(() => {
    if (isOpen && logs.length > 0) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs.length, isOpen])

  const handleClose = useCallback(() => {
    onClose?.() ?? onToggle?.()
  }, [onClose, onToggle])

  if (!isOpen) {
    return (
      <button
        onClick={handleClose}
        aria-label="Open debug panel"
        className="fixed right-4 top-4 bg-slate-800 border border-slate-700 text-slate-400 px-3 py-2 rounded-lg text-xs hover:bg-slate-700 transition-colors z-50"
      >
        🔧 {t.debug?.title || 'Debug'} {status === 'running' && '●'}
      </button>
    )
  }

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 28, stiffness: 400 }}
      className="w-80 border-l border-slate-800/60 bg-[#0a0a0f] flex flex-col h-full shadow-2xl"
    >
      {/* HEADER */}
      <div className="bg-slate-900/50 px-4 py-3 border-b border-slate-800/60 flex items-center justify-between">
        <span className="text-sm font-semibold">🔧 {t.debug?.title || 'Debug'}</span>
        <button
          onClick={handleClose}
          aria-label="Close debug panel"
          className="text-slate-400 hover:text-white text-xl leading-none transition-colors"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* STATUS */}
        <div className="p-4 space-y-3 border-b border-slate-800/60">
          <Row label={t.debug?.status || 'Status'} value={status.toUpperCase()} />
          <Row label={t.debug?.model || 'Model'} value={modelName} color="violet" />
          <Row label={t.debug?.backend || 'Backend'} value={backendDisplay} />
          <Row label={t.debug?.elapsed || 'Elapsed'} value={`${elapsedSeconds}s`} />
          <Row label={t.debug?.tokens || 'Tokens'} value={tokenCount} color="violet" bold />
        </div>

        {/* PROGRESS */}
        {steps.length > 0 && status === 'running' && (
          <div className="p-4 border-b border-slate-800/60">
            <div className="flex justify-between text-xs mb-2">
              <span>
                {typeof t.steps?.stepLabel === 'function'
                  ? t.steps.stepLabel(activeStepNumber, steps.length)
                  : `Step ${activeStepNumber}/${steps.length}`}
              </span>
              <span>{elapsedSeconds}s</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-violet-500"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
          </div>
        )}

        {/* STEPS */}
        <div className="p-4 border-b border-slate-800/60">
          <div className="text-xs text-slate-500 mb-3">
            {t.debug?.agentExecution || 'Agent Execution'}
          </div>
          {steps.map((step, i) => (
            <div key={step.id} className="flex gap-3 text-sm mb-3 last:mb-0">
              <div className="w-5 h-5 flex items-center justify-center rounded-full text-xs bg-slate-800 flex-shrink-0">
                {step.status === 'done'
                  ? '✓'
                  : step.status === 'active'
                    ? '●'
                    : i + 1}
              </div>
              <div className="min-w-0">
                <div
                  className={step.status === 'active' ? 'text-white' : 'text-slate-400'}
                >
                  {step.title}
                </div>
                {step.detail && (
                  <div className="text-xs text-slate-500 mt-0.5">{step.detail}</div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* CURRENT CODE */}
        {currentCode && (
          <div className="p-4 border-b border-slate-800/60">
            <div className="text-xs text-slate-500 mb-2">
              {t.debug?.generatedCode || 'Generated Code'}
            </div>
            <pre className="max-h-64 overflow-auto text-[10px] text-slate-300 bg-slate-900/50 p-3 rounded font-mono whitespace-pre-wrap border border-slate-800">
              {currentCode.length > 2000
                ? currentCode.slice(-2000) + '\n... (truncated)'
                : currentCode}
            </pre>
          </div>
        )}

        {/* LIVE LOGS - Virtualized */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="px-4 py-2 border-b border-slate-800 flex justify-between items-center">
            <span className="text-xs text-slate-500">
              {t.debug?.liveLogs || 'Live Logs'}
            </span>
            {onClearLogs && (
              <button
                onClick={onClearLogs}
                aria-label="Clear logs"
                className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
              >
                {t.debug?.clear || 'Clear'}
              </button>
            )}
          </div>
          <VirtualizedLogs
            logs={logs || []}
            lineHeight={18}
            containerHeight={300}
          />
        </div>
      </div>

      {/* ERROR */}
      {lastErrorMsg && status === 'error' && (
        <div className="p-3 text-xs text-red-400 border-t border-red-900/30 bg-red-950/30">
          ⚠ {lastErrorMsg.split('\n')[0]}
        </div>
      )}
    </motion.div>
  )
}

// =====================
// HELPER
// =====================
function Row({
  label,
  value,
  color,
  bold,
}: {
  label: string
  value: React.ReactNode
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
