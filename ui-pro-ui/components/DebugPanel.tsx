'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { motion } from 'framer-motion'

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
  onClearLogs?: () => void
  status?: 'idle' | 'running' | 'completed' | 'error'
  modelName?: string
  elapsedSeconds?: number
  tokenCount?: number
  connectionStatus?: 'connected' | 'connecting' | 'error'
  lastErrorMsg?: string
  currentStep?: number
  logs?: string[]
  subscribeToStore?: boolean
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
}: DebugPanelProps) {
  const [localTokenCount, setLocalTokenCount] = useState(propTokenCount)
  const logsEndRef = useRef<HTMLDivElement>(null)
  
  // CRITICAL FIX: Sync with parent prop changes
  useEffect(() => {
    if (propTokenCount !== localTokenCount) {
      setLocalTokenCount(propTokenCount)
    }
  }, [propTokenCount, localTokenCount])
  
  const completed = useMemo(() => steps.filter(s => s.status === 'done').length, [steps])
  const progress = useMemo(() => 
    steps.length > 0 ? Math.round((completed / steps.length) * 100) : 0,
    [steps, completed]
  )
  const activeIdx = useMemo(() => 
    steps.findIndex(s => s.status === 'active') !== -1 
      ? steps.findIndex(s => s.status === 'active') 
      : currentStep,
    [steps, currentStep]
  )

  // Scroll on logs change only when panel is open
  useEffect(() => {
    if (isOpen && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, isOpen])
  
  // Debug: log when status changes
  useEffect(() => {
    console.log('[DebugPanel] Status:', status, 'steps:', steps.length)
  }, [status, steps])
  
  const closeFn = useCallback(() => {
    if (onClose) onClose()
    else if (onToggle) onToggle()
  }, [onClose, onToggle])

  if (!isOpen) return (
    <button onClick={closeFn} className="fixed right-4 top-4 bg-slate-800 border border-slate-700 text-slate-400 px-3 py-2 rounded-lg text-xs hover:bg-slate-700 z-50">
      🔧 Debug {status === 'running' && '●'}
    </button>
  )

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      transition={{ type: 'spring', damping: 28, stiffness: 400 }}
      className="w-80 border-l border-slate-800/60 bg-[#0a0a0f] flex flex-col h-full shadow-2xl"
    >
      {/* Header */}
      <div className="bg-slate-900/50 px-4 py-3 border-b border-slate-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-violet-400">🔧</span>
          <span className="font-semibold text-sm">Debug Panel</span>
        </div>
        <button onClick={closeFn} className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded hover:bg-slate-800">✕</button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Status Bar */}
        <div className="p-4 border-b border-slate-800/60 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Status</span>
            <span className={status === 'running' ? 'text-emerald-400' : status === 'completed' ? 'text-blue-400' : 'text-red-400'}>
              {status === 'running' ? '● RUNNING' : status.toUpperCase()}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Model</span>
            <span className="font-mono text-violet-400">{modelName}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Backend</span>
            <span className="text-amber-400">🦙 Ollama</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">Elapsed</span>
            <span className="font-mono text-slate-300">{elapsedSeconds}s</span>
          </div>
          <div className="flex items-center justify-between text-xs font-bold">
            <span className="text-slate-500">Tokens</span>
            <span className="font-mono text-violet-400">{localTokenCount}</span>
          </div>
        </div>

        {/* Progress */}
        {(status === 'running' || status === 'completed') && steps.length > 0 && (
          <div className="p-4 border-b border-slate-800/60 bg-violet-950/10">
            <div className="flex justify-between text-[10px] mb-2.5">
              <span className="text-violet-400">Step {(activeIdx !== -1 ? activeIdx + 1 : 1)} / {steps.length}</span>
              <span className="text-slate-500 font-mono">{elapsedSeconds}s</span>
            </div>
            <div className="h-1.5 bg-slate-800/60 rounded-full overflow-hidden">
              <motion.div className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500" initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ duration: 0.8, ease: 'easeInOut' }} />
            </div>
          </div>
        )}

        {/* Steps */}
        <div className="px-4 py-3 border-b border-slate-800/60">
          <div className="text-xs text-slate-500 mb-3 font-semibold">Agent Execution</div>
          <div className="space-y-2.5">
            {steps.map((step, idx) => (
              <motion.div key={step.id || idx} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx * 0.05 }} className="flex items-start gap-3 text-sm">
                <div className={`mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-xs ${step.status === 'done' ? 'bg-emerald-900/50 text-emerald-400' : step.status === 'active' ? 'bg-violet-900/50 text-violet-400' : 'bg-slate-800/50 text-slate-500'}`}>
                  {step.status === 'done' ? '✓' : step.status === 'active' ? '●' : `#${idx + 1}`}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={step.status === 'active' ? 'text-white' : 'text-slate-400'}>{step.title}</p>
                  {step.detail && <p className="text-xs text-slate-500 mt-0.5">{step.detail}</p>}
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Logs */}
        <div className="flex-1 flex flex-col min-h-0 bg-slate-950/30">
          <div className="px-4 py-2.5 border-b border-slate-800/60 flex justify-between items-center">
            <span className="text-xs font-medium text-slate-500">Live Logs</span>
            <button onClick={() => {
              if (onClearLogs) {
                onClearLogs()
              }
            }} className="text-slate-500 hover:text-slate-300 text-[10px]">Clear</button>
          </div>
          <div ref={logsEndRef} className="flex-1 p-4 font-mono text-[10px] overflow-y-auto space-y-1">
            {logs.length === 0 ? <span className="text-slate-600 italic">Waiting...</span> : logs.map((log, i) => <div key={i}>{log}</div>)}
          </div>
        </div>
      </div>

      {lastErrorMsg && (
        <div className="px-4 py-3 bg-red-950/10 border-t border-red-900/30">
          <div className="text-xs text-red-400">⚠ {lastErrorMsg.split('\n')[0]}</div>
        </div>
      )}
    </motion.div>
  )
}
