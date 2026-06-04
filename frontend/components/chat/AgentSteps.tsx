// AgentSteps.tsx (chat/)
// Role: Renders agent execution steps with progress bar, status icons, and smooth animations

'use client'

import { memo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AgentStep } from '@/lib/types'
import { useEnableThinking } from '../settings/hooks/useEnableThinking'

interface AgentStepsProps {
  steps: AgentStep[]
  className?: string
}

const statusConfig: Record<string, { icon: string; color: string; bgColor: string }> = {
  pending: { icon: '⏳', color: 'text-slate-500', bgColor: 'bg-slate-700' },
  active: { icon: '🧠', color: 'text-violet-400', bgColor: 'bg-violet-500/20' },
  done: { icon: '✅', color: 'text-emerald-400', bgColor: 'bg-emerald-500/20' },
  error: { icon: '⚠️', color: 'text-red-400', bgColor: 'bg-red-500/20' },
}

export const AgentSteps = memo(function AgentSteps({
  steps,
  className = ''
}: AgentStepsProps) {
  const completedCount = steps.filter(s => s.status === 'done').length
  const progress = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0
  const hasActiveStep = steps.some(s => s.status === 'active')
  // Mirror the send-button brain indicator here so the user sees the
  // thinking-mode reminder while the LLM is being called. The brain
  // pulses on the active step (when an LLM call is in flight) so the
  // "thinking is OFF" reminder is contextually tied to the moment of
  // generation, not just a passive UI badge.
  const { enabled: thinkingEnabled } = useEnableThinking()
  const thinkingOff = !thinkingEnabled

  return (
    <div className={`bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-violet-500/30 rounded-2xl p-5 shadow-lg shadow-violet-500/10 ${className}`}>
      {/* Header with Thinking Process Badge */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          {/* Animated robot icon */}
          <div className="relative">
            <motion.span 
              className="text-2xl"
              animate={hasActiveStep ? { scale: [1, 1.1, 1] } : {}}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              🤖
            </motion.span>
            {hasActiveStep && (
              <motion.span
                className="absolute -top-1 -right-1 w-2 h-2 bg-violet-500 rounded-full"
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ repeat: Infinity, duration: 1 }}
              />
            )}
          </div>
          <div>
            {/* Thinking Process Badge */}
            <div className="flex items-center gap-2">
              <motion.span
                className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 font-medium"
                animate={hasActiveStep ? { backgroundColor: ['rgba(139, 92, 246, 0.2)', 'rgba(139, 92, 246, 0.4)', 'rgba(139, 92, 246, 0.2)'] } : {}}
                transition={{ repeat: Infinity, duration: 1.5 }}
              >
                🧠 Thinking Process
              </motion.span>
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {completedCount} of {steps.length} steps completed
            </div>
          </div>
        </div>

        <div className="text-right">
          <div className="text-xs font-mono text-violet-400 font-bold">{progress}%</div>
        </div>
      </div>

      {/* Progress Bar with glow effect */}
      <div className="h-1.5 bg-slate-700 rounded-full mb-5 overflow-hidden">
        <motion.div
          className="h-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-violet-500"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        />
        {/* Glow effect behind progress bar */}
        {hasActiveStep && (
          <motion.div
            className="h-1.5 bg-gradient-to-r from-violet-500 to-fuchsia-500 blur-sm"
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            style={{ marginTop: '-6px' }}
          />
        )}
      </div>

      {/* Steps List with enhanced active state */}
      <div className="space-y-2">
        <AnimatePresence initial={false}>
          {steps.map((step, index) => {
            const config = statusConfig[step.status]
            const isActive = step.status === 'active'

            return (
              <motion.div
                key={step.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className={`
                  flex items-center gap-3 text-sm rounded-lg px-3 py-2 transition-all
                  ${isActive ? 'bg-violet-500/10 border border-violet-500/30 shadow-md shadow-violet-500/10' : ''}
                  ${config.color}
                `}
              >
                {/* Status icon with background */}
                <div className={`w-7 h-7 rounded-full ${config.bgColor} flex items-center justify-center text-sm`}>
                  {isActive ? (
                    <motion.span
                      animate={{ rotate: [0, 360] }}
                      transition={{ repeat: Infinity, duration: 3, ease: 'linear' }}
                    >
                      {config.icon}
                    </motion.span>
                  ) : (
                    <span>{config.icon}</span>
                  )}
                </div>
                
                <span className={`flex-1 ${isActive ? 'text-white font-medium' : ''}`}>
                  {step.title}
                </span>

                {isActive && (
                  <div className="flex items-center gap-2">
                    {thinkingOff && (
                      <motion.span
                        className="text-sm"
                        aria-hidden="true"
                        animate={{ scale: [1, 1.2, 1], opacity: [0.7, 1, 0.7] }}
                        transition={{ repeat: Infinity, duration: 1.6, ease: 'easeInOut' }}
                        title="Thinking mode is OFF — the model jumps straight to the answer"
                      >
                        🧠
                      </motion.span>
                    )}
                    <motion.div
                      animate={{ opacity: [1, 0.4, 1], scale: [1, 1.05, 1] }}
                      transition={{ repeat: Infinity, duration: 1.5 }}
                      className="text-xs px-2 py-1 bg-violet-500 text-white rounded-full font-medium"
                    >
                      ● Active
                    </motion.div>
                  </div>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
})

AgentSteps.displayName = 'AgentSteps'