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
}

export function DebugPanel({ steps = [], isOpen = true, onToggle, status = 'idle' }: DebugPanelProps) {
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
  
  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: isOpen ? 0 : '100%' }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className={`h-64 border-slate-800 bg-slate-950/50 flex flex-col`}
    >
      {/* Header */}
      <motion.div
        className="bg-slate-900 px-4 py-2.5 flex items-center justify-between border-b border-slate-800 cursor-pointer"
        whileHover={{ backgroundColor: 'rgba(0,0,0,0.2)' }}
      >
        {/* Left side */}
        <div className="flex items-center gap-3">
          <span>{expanded ? '▼' : '▲'}</span>
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
        {expanded && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
          >
            {/* Steps */}
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
                  currentStatus === 'running'
                    ? 'text-green-400'
                    : currentStatus === 'error'
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
                    currentStatus === 'running'
                      ? 'bg-green-500'
                      : currentStatus === 'error'
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

  return (
    <div className="w-72 bg-slate-900 border-l border-slate-800 flex flex-col">
      {/* Header */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white">🧠 Agent Debug</h2>
        <button
          onClick={onToggle}
          className="text-slate-500 hover:text-slate-300 text-xs"
        >
          ✕
        </button>
      </div>

      {/* Steps */}
      <div className="flex-1 overflow-y-auto p-3">
        {steps.length === 0 ? (
          <div className="text-xs text-slate-500">
            Agent steps will appear here...
          </div>
        ) : (
          <div className="space-y-2">
            {steps.map((step, index) => (
              <div
                key={step.id}
                className={`p-2 rounded-lg text-xs ${
                  step.status === 'done'
                    ? 'bg-green-900/30 text-green-400'
                    : step.status === 'active'
                    ? 'bg-blue-900/30 text-blue-400'
                    : 'bg-slate-800/50 text-slate-500'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-slate-700 flex items-center justify-center">
                    {step.status === 'done' ? '✓' : index + 1}
                  </span>
                  <span className={step.status === 'active' ? 'animate-pulse' : ''}>
                    {step.title}
                  </span>
                </div>
                {step.detail && (
                  <div className="mt-1 pl-7 text-slate-500">{step.detail}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="p-3 border-t border-slate-800 text-xs text-slate-500">
        <div className="flex justify-between">
          <span>Steps:</span>
          <span className="text-slate-400">{steps.filter(s => s.status === 'done').length}/{steps.length}</span>
        </div>
        <div className="flex justify-between mt-1">
          <span>Status:</span>
          <span className="text-green-400">● Active</span>
        </div>
      </div>
    </div>
  )
}