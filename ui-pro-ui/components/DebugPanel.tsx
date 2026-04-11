'use client'

// Debug Panel - Agent visualization

import { useState } from 'react'

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
}

export function DebugPanel({ steps = [], isOpen = true, onToggle }: DebugPanelProps) {
  const [expanded, setExpanded] = useState(true)

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