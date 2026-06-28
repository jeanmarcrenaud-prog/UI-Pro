// CustomNode.tsx
// React Flow custom node for Agent Canvas — icons, metrics, glassmorphism, animations

'use client'

import { Handle, Position, type NodeProps } from 'reactflow'
import { motion } from 'framer-motion'
import type { CanvasStep } from '@/lib/stores/agentCanvasStore'
import { getIcon, getStatusColor, getNodeClasses } from './nodeStyles'

/** Module-level animation variants (stable ref, survives HMR) */
const nodeVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.4, ease: [0.23, 1.0, 0.32, 1.0] as const },
  },
}

export default function CustomNode({ id, data, selected }: NodeProps<CanvasStep>) {
  const { status, name, modelUsed, durationMs, tokens } = data
  const Icon = getIcon(name)
  const colorClass = getStatusColor(status || 'pending')
  const classes = getNodeClasses(id, name, status || 'pending')

  const DISPLAY_NAMES: Record<string, string> = {
    'step-orchestrator': 'Orchestrator',
    'step-analyzing': 'Analyze',
    'step-planning': 'Plan',
    'step-coding': 'Code',
    'step-reviewing': 'Review',
    'step-executing': 'Execute',
    'step-fixing': 'Fix',
    'step-execution_success': 'Completed',
    'step-execution_failed': 'Failed',
    'step-max_attempts_reached': 'Max Attempts',
    'step-no_code_short_circuit': 'No Code',
  }
  const displayName = DISPLAY_NAMES[name] || name.replace(/^step-/, '').replace(/_/g, ' ')

  return (
    <motion.div
      className={`${classes} ${selected ? 'ring-2 ring-white/70' : ''}`}
      variants={nodeVariants}
      initial="hidden"
      animate="visible"
      whileHover={{ scale: 1.02, transition: { duration: 0.2 } }}
      whileTap={{ scale: 0.98 }}
    >
      {/* Left handle (target) */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !border-2 !border-gray-600 !bg-gray-900"
      />

      <div className="flex items-start gap-4">
        {/* Icon */}
        <motion.div
          className={`mt-0.5 ${colorClass}`}
          animate={status === 'running' ? { rotate: 360 } : {}}
          transition={
            status === 'running'
              ? { duration: 1.5, repeat: Infinity, ease: 'linear' }
              : {}
          }
        >
          <Icon size={28} strokeWidth={1.8} />
        </motion.div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Label */}
          <div className="font-semibold text-white tracking-tight text-base">
            {displayName}
          </div>

          {/* Model */}
          {modelUsed && (
            <div className="text-xs text-slate-400 mt-0.5 font-mono">{modelUsed}</div>
          )}

          {/* Metrics */}
          {(durationMs || tokens) && (
            <motion.div
              className="mt-2.5 text-xs text-white/50 font-mono flex gap-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              {durationMs != null && <span>⏱ {Math.round(durationMs)}ms</span>}
              {tokens != null && <span>🧠 {tokens.toLocaleString()} tokens</span>}
            </motion.div>
          )}

          {/* Running indicator */}
          {status === 'running' && (
            <motion.div
              className="mt-2 flex items-center gap-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <span className="w-2 h-2 bg-sky-400 rounded-full animate-pulse" />
              <span className="text-xs text-sky-400 font-medium">En cours...</span>
            </motion.div>
          )}

          {/* Approval indicator */}
          {status === 'awaiting_approval' && (
            <div className="mt-2 text-xs text-amber-400 font-medium">
              ⏳ En attente d&apos;approbation
            </div>
          )}
        </div>
      </div>

      {/* Right handle (source) */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !border-2 !border-gray-600 !bg-gray-900"
      />
    </motion.div>
  )
}
