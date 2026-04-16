'use client'

import { useState, useMemo, useEffect } from 'react'
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
  modelName?: string
  currentStep?: number
  elapsedSeconds?: number
  tokenCount?: number
  connectionStatus?: 'connected' | 'connecting' | 'error'
  lastError?: string
}

export function DebugPanel({ 
  steps = [], 
  isOpen = true, 
  onToggle, 
  status = 'idle',
  modelName = 'gemma4',
  currentStep = 0,
  elapsedSeconds = 0,
  tokenCount = 0,
  connectionStatus = 'connected',
  lastError
}: DebugPanelProps) {
  const [expanded, setExpanded] = useState(true)
  const [logs, setLogs] = useState<string[]>([])

  // Capture console logs for debugging
  useEffect(() => {
    const originalLog = console.log
    const originalError = console.error
    const originalWarn = console.warn
    
    const addLog = (type: string, ...args: unknown[]) => {
      const timestamp = new Date().toLocaleTimeString()
      const msg = args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')
      setLogs(prev => [...prev.slice(-50), `[${timestamp}] ${type}: ${msg}`])
    }
    
    console.log = (...args) => addLog('LOG', ...args)
    console.error = (...args) => addLog('ERR', ...args)
    console.warn = (...args) => addLog('WARN', ...args)
    
    return () => {
      console.log = originalLog
      console.error = originalError
      console.warn = originalWarn
    }
  }, [])

  const completed = steps.filter(s => s.status === 'done').length
  const total = steps.length
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed right-4 top-4 bg-slate-800 border border-slate-700 text-slate-400 px-3 py-2 rounded-lg text-xs hover:bg-slate-700 transition-colors z-50"
      >
        🔧 Debug {status === 'running' && '●'}
      </button>
    )
  }

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: isOpen ? 0 : '100%' }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className={`h-[450px] w-80 border-slate-800 bg-slate-950/50 flex flex-col`}
    >
      {/* Header */}
      <motion.div
        className="bg-slate-900 px-4 py-2.5 flex items-center justify-between border-b border-slate-800 cursor-pointer"
        whileHover={{ backgroundColor: 'rgba(0,0,0,0.2)' }}
      >
        <div className="flex items-center gap-3">
          <span onClick={() => setExpanded(!expanded)}>{expanded ? '▼' : '▲'}</span>
          <span className="text-slate-400 text-xs">Debug</span>
        </div>

        <div className="flex items-center gap-2">
          <span className={`text-xs ${status === 'running' ? 'text-green-400' : status === 'error' ? 'text-red-400' : 'text-slate-400'}`}>
            {status === 'running' ? '● Running' : status === 'error' ? '⚠ Error' : '○ Idle'}
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
        <motion.div
          key="debug-info"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex-1 overflow-y-auto"
        >
          {/* Connection & Model Status */}
          <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/20">
            <div className="text-xs text-slate-500 mb-2 font-medium">Connection</div>
            
            {/* Connection Status */}
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-500">WebSocket</span>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${
                  connectionStatus === 'connected' ? 'bg-green-500' :
                  connectionStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' :
                  'bg-red-500'
                }`} />
                <span className={
                  connectionStatus === 'connected' ? 'text-green-400' :
                  connectionStatus === 'connecting' ? 'text-yellow-400' :
                  'text-red-400'
                }>
                  {connectionStatus === 'connected' ? 'Connected' : 
                   connectionStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
                </span>
              </div>
            </div>

            {/* Model */}
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-500">Model</span>
              <span className="text-violet-400 font-mono">{modelName}</span>
            </div>

            {/* Backend indicator */}
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-500">Backend</span>
              <span className={modelName.includes('GGUF') ? 'text-amber-400' : 'text-blue-400'}>
                {modelName.includes('GGUF') ? '🍋 Lemonade' : '🦙 Ollama'}
              </span>
            </div>

            {/* Token Counter */}
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-500">Tokens</span>
              <span className="text-violet-400">{tokenCount.toLocaleString()}</span>
            </div>

            {/* Elapsed Time */}
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-slate-500">Elapsed</span>
              <span className="text-slate-300">{elapsedSeconds}s</span>
            </div>

            {/* Progress Status */}
            {status === 'running' && (
              <div className="mt-2 p-2 bg-violet-900/30 border border-violet-800/50 rounded text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-violet-300">Step {currentStep + 1}/{steps.length || 1}</span>
                  <span className="text-violet-400 font-mono">{elapsedSeconds}s</span>
                </div>
                <div className="mt-1 h-1 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-violet-500 transition-all duration-500"
                    style={{ width: `${((currentStep + 1) / (steps.length || 1)) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Error Display */}
            {lastError && (
              <div className="mt-2 p-2 bg-red-900/30 border border-red-800 rounded text-xs text-red-300">
                <span className="font-medium">Error: </span>{lastError}
              </div>
            )}

            {/* Status indicator */}
            {status === 'running' && (
              <div className="mt-2 flex items-center gap-2 text-xs text-green-400">
                <motion.span 
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ repeat: Infinity, duration: 1.5 }}
                  className="w-2 h-2 bg-green-500 rounded-full"
                />
                <span>Streaming response...</span>
              </div>
            )}
          </div>

          {/* Steps Section */}
          {expanded && (
            <div className="border-b border-slate-800">
              <div className="px-4 py-2 text-xs text-slate-500 font-medium">Agent Steps</div>
              <div className="px-4 pb-3 space-y-2">
                {total === 0 ? (
                  <div className="text-xs text-slate-600 py-2">
                    Agent steps will appear here when processing.
                  </div>
                ) : (
                  steps.map((step, idx) => (
                    <motion.div
                      key={step.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-center gap-2 text-xs"
                    >
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                        step.status === 'done' ? 'bg-green-900 text-green-400' :
                        step.status === 'active' ? 'bg-violet-900 text-violet-400' :
                        'bg-slate-800 text-slate-500'
                      }`}>
                        {step.status === 'done' ? '✓' : step.status === 'active' ? (idx + 1) : '-'}
                      </span>
                      <span className={
                        step.status === 'active' ? 'text-white' :
                        step.status === 'done' ? 'text-slate-400' :
                        'text-slate-600'
                      }>
                        {step.title}
                      </span>
                    </motion.div>
                  ))
                )}
              </div>
              
              {/* Progress bar */}
              {total > 0 && (
                <div className="px-4 pb-3">
                  <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                    <span>Progress</span>
                    <span>{percent}%</span>
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${percent}%` }}
                      className={`h-full rounded-full ${status === 'running' ? 'bg-green-500' : status === 'error' ? 'bg-red-500' : 'bg-slate-600'}`}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Live Logs */}
          {expanded && (
            <div className="flex-1 min-h-0">
              <div className="px-4 py-2 flex items-center justify-between text-xs text-slate-500 font-medium border-b border-slate-800">
                <span>Live Logs</span>
                <button 
                  onClick={() => setLogs([])}
                  className="text-slate-600 hover:text-slate-400"
                >
                  Clear
                </button>
              </div>
              <div className="h-32 overflow-y-auto px-4 py-2 font-mono text-[10px] space-y-0.5">
                {logs.length === 0 ? (
                  <span className="text-slate-600">No logs yet...</span>
                ) : (
                  logs.map((log, i) => (
                    <div 
                      key={i} 
                      className={`${
                        log.includes('ERR') ? 'text-red-400' :
                        log.includes('WARN') ? 'text-yellow-400' :
                        'text-slate-400'
                      }`}
                    >
                      {log}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  )
}
