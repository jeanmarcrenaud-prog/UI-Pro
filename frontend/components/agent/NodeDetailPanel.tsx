// components/agent/NodeDetailPanel.tsx
// Slide-over detail panel for a selected graph node

'use client'

import { motion, AnimatePresence } from 'framer-motion'

interface NodeDetailPanelProps {
  nodeId: string | null
  step?: {
    id: string
    title: string
    status: string
    duration?: number
    tokens?: number
    detail?: string
  } | null
  nodeDef?: {
    label: string
    description: string
  } | null
  onClose: () => void
}

const STATUS_COLORS: Record<string, string> = {
  active: 'text-violet-400',
  done: 'text-emerald-400',
  error: 'text-red-400',
  completed: 'text-emerald-400',
  running: 'text-violet-400',
}

function formatTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`
}

export function NodeDetailPanel({ nodeId, step, nodeDef, onClose }: NodeDetailPanelProps) {
  if (!nodeId || !step) return null

  const statusColor = STATUS_COLORS[step.status] || 'text-slate-400'

  return (
    <AnimatePresence>
      <motion.div
        key={nodeId}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{ duration: 0.2 }}
        className="absolute top-4 right-4 w-72 bg-slate-900/95 border border-slate-700 rounded-xl shadow-xl p-4 z-10 backdrop-blur-sm"
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-white">
            {nodeDef?.label || step.title}
          </span>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors p-0.5"
            aria-label="Close detail panel"
          >
            ✕
          </button>
        </div>

        {/* Details */}
        <div className="space-y-2 text-xs">
          {/* Status */}
          <div className="flex justify-between items-center">
            <span className="text-slate-500">Status</span>
            <span className={`font-medium ${statusColor}`}>
              {step.status === 'done' ? 'Completed' :
               step.status === 'active' ? 'Running' :
               step.status === 'error' ? 'Failed' :
               step.status}
            </span>
          </div>

          {/* Duration */}
          {step.duration !== undefined && (
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Duration</span>
              <span className="text-slate-300 font-mono">{step.duration.toFixed(1)}s</span>
            </div>
          )}

          {/* Tokens */}
          {step.tokens !== undefined && step.tokens > 0 && (
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Tokens</span>
              <span className="text-slate-300 font-mono">{formatTokens(step.tokens)}</span>
            </div>
          )}

          {/* Detail text */}
          {step.detail && (
            <div className="pt-2 mt-2 border-t border-slate-700/50">
              <span className="text-slate-500 block mb-1">Detail</span>
              <span className="text-slate-300 text-[11px] leading-relaxed">{step.detail}</span>
            </div>
          )}

          {/* Description */}
          {nodeDef?.description && (
            <div className="pt-2 mt-2 border-t border-slate-700/50">
              <span className="text-slate-500 block mb-1">Description</span>
              <span className="text-slate-400 text-[11px] leading-relaxed">{nodeDef.description}</span>
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
