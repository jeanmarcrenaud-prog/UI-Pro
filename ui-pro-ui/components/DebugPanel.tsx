'use client'

import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface AgentStep {
  id: string
  title: string
  detail?: string
  status: 'pending' | 'active' | 'done'
}

interface DebugPanelProps {
  steps?: AgentStep[]
  isOpen?: boolean
  onToggle?: () => void
  status?: 'idle' | 'running' | 'error'
  // NEW: Additional debug info props
  modelName?: string
  connectionStatus?: 'connected' | 'disconnected' | 'connecting' | 'error'
  messageCount?: number
  lastError?: string
  startTime?: number  // timestamp when request started
}

export function DebugPanel({ 
  steps = [], 
  isOpen = true, 
  onToggle, 
  status = 'idle',
  modelName = 'gemma',
  connectionStatus = 'connected',
  messageCount = 0,
  lastError,
  startTime
}: DebugPanelProps) {
  const [expanded, setExpanded] = useState(true)

  // Truncate long details
  const truncateDetail = useMemo(
    () => (text?: string) => {
      if (!text) return ''
      return text.length > 120 ? text.slice(0, 120) + '…' : text
    },
    []
  )

  // Compute stats
  const completed = steps.filter(s => s.status === 'done').length
  const total = steps.length
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0

  // Calculate elapsed time if startTime provided
  const elapsed = useMemo(() => {
    if (!startTime) return null
    return Math.round((Date.now() - startTime) / 1000)
  }, [startTime])

  // Si le panneau n'est pas ouvert, afficher uniquement le bouton
  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed right-4 top-4 bg-slate-800 border border-slate-700 text-slate-400 px-3 py-2 rounded-lg text-xs hover:bg-slate-700 transition-colors z-50"
      >
        🔧 Debug
      </button>
    )
  }

  // Sinon, afficher le panneau complet
  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: isOpen ? 0 : '100%' }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className={`h-[400px] w-72 border-slate-800 bg-slate-950/50 flex flex-col`}
    >
      {/* Header */}
      <motion.div
        className="bg-slate-900 px-4 py-2.5 flex items-center justify-between border-b border-slate-800 cursor-pointer"
        whileHover={{ backgroundColor: 'rgba(0,0,0,0.2)' }}
      >
        {/* Left side */}
        <div className="flex items-center gap-3">
          <span onClick={() => setExpanded(!expanded)}>{expanded ? '▼' : '▲'}</span>
          <span className="text-slate-400 text-xs">Debug</span>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          <span className={`text-xs ${
            status === 'running'
              ? 'text-green-400'
              : status === 'error'
              ? 'text-red-400'
              : 'text-slate-400'
          }`}>
            {status === 'running'
              ? '● Processing...'
              : status === 'error'
              ? '⚠ Error'
              : '○ Idle'}
          </span>
          <button
            onClick={onToggle}
            className="text-slate-500 hover:text-slate-300 text-xs px-2 py-1 rounded hover:bg-slate-800 transition-colors"
          >
            {expanded ? 'Hide' : 'Show'}
          </button>
        </div>
      </motion.div>

      {/* Collapsible content */}
      <AnimatePresence>
        {/* NEW: Debug Info Section */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="px-4 py-3 border-b border-slate-800 bg-slate-900/20"
        >
          {/* Connection Status */}
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-slate-500">Connection</span>
            <span className={`flex items-center gap-1.5 ${
              connectionStatus === 'connected' ? 'text-green-400' :
              connectionStatus === 'connecting' ? 'text-yellow-400' :
              connectionStatus === 'error' ? 'text-red-400' :
              'text-slate-400'
            }`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current" />
              {connectionStatus === 'connected' ? 'Connected' :
               connectionStatus === 'connecting' ? 'Connecting...' :
               connectionStatus === 'error' ? 'Error' :
               'Disconnected'}
            </span>
          </div>

          {/* Model Name */}
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-slate-500">Model</span>
            <span className="text-slate-300 font-mono">{modelName}</span>
          </div>

          {/* Messages */}
          <div className="flex items-center justify-between text-xs mb-2">
            <span className="text-slate-500">Messages</span>
            <span className="text-slate-300">{messageCount}</span>
          </div>

          {/* Elapsed Time */}
          {elapsed !== null && (
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-500">Elapsed</span>
              <span className="text-slate-300">{elapsed}s</span>
            </div>
          )}

          {/* Error Display */}
          {lastError && (
            <div className="mt-2 p-2 bg-red-900/30 border border-red-800 rounded text-xs text-red-300">
              <span className="font-medium">Error: </span>{lastError}
            </div>
          )}
        </motion.div>

        {/* Steps Section */}
        {expanded && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
          >
            {/* Steps Section */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {total === 0 ? (
                // Placeholder
                <div className="h-full flex flex-col items-center justify-center text-slate-500">
                  <span className="text-sm mb-2">
                    Agent steps (analyze → plan → code → review → run)
                  </span>
                  <span className="text-xs text-slate-600">
                    will appear here when an advanced agent is active.
                  </span>
                </div>
              ) : (
                steps.map((step) => (
                  <motion.div
                    key={step.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="pl-4 border-l-2 border-slate-800"
                  >
                    {/* Step header */}
                    <div className="flex items-center gap-3 text-sm">
                      <span className="w-6 text-center">
                        {step.status === 'done' ? '✅' : step.status === 'active' ? '⚙️' : '⏳'}
                      </span>

                      <span className="flex-1">
                        <span
                          className={step.status === 'active' ? 'text-white font-medium' : 'text-slate-400'}
                        >
                          {step.title}
                        </span>
                        {step.status === 'active' && ' (active)'}
                      </span>

                      <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full">
                        {step.status === 'done' ? '✓' : step.status === 'active' ? '→' : '-'}
                      </span>
                    </div>

                    {/* Optional detail */}
                    {step.detail && (
                      <div className="mt-1 pl-7 text-slate-500 text-xs">
                        {truncateDetail(step.detail)}
                      </div>
                    )}
                  </motion.div>
                ))
              )}
            </div>

            {/* Footer with progress */}
            <div className="px-4 py-2.5 border-t border-slate-800 bg-slate-900/30">
              <div className="flex items-center justify-between text-xs text-slate-500 mb-1.5">
                <span>Progress: {completed}/{total} steps completed</span>
                <span className={
                  status === 'running'
                    ? 'text-green-400'
                    : status === 'error'
                    ? 'text-red-400'
                    : 'text-slate-500'
                }>
                  {percent}%
                </span>
              </div>

              {/* Progress bar */}
              <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${percent}%` }}
                  transition={{ type: 'spring', damping: 15 }}
                  className={`h-full rounded-full ${
                    status === 'running'
                      ? 'bg-green-500'
                      : status === 'error'
                      ? 'bg-red-500'
                      : 'bg-slate-600'
                  }`}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}