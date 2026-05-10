// AgentSteps.tsx (chat/)
// Role: Renders agent execution steps with progress bar, status icons, and smooth animations

'use client'

import { memo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface Step {
  id: string
  title: string
  status: 'pending' | 'active' | 'done'
}

interface AgentStepsProps {
  steps: Step[]
  className?: string
}

const statusConfig = {
  pending: { icon: '⏳', color: 'text-slate-500' },
  active: { icon: '⚙️', color: 'text-violet-400' },
  done: { icon: '✅', color: 'text-emerald-400' },
}

export const AgentSteps = memo(function AgentSteps({ 
  steps, 
  className = '' 
}: AgentStepsProps) {
  const completedCount = steps.filter(s => s.status === 'done').length
  const progress = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0

  return (
    <div className={`bg-slate-900/90 border border-slate-700 rounded-2xl p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-xl">🤖</span>
          <div>
            <div className="text-sm font-medium text-white">Agent Execution</div>
            <div className="text-xs text-slate-500">
              {completedCount} of {steps.length} steps completed
            </div>
          </div>
        </div>

        <div className="text-right">
          <div className="text-xs text-emerald-400 font-mono">{progress}%</div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="h-1 bg-slate-800 rounded-full mb-5 overflow-hidden">
        <motion.div
          className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        />
      </div>

      {/* Steps List */}
      <div className="space-y-3">
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
                className={`flex items-center gap-3 text-sm transition-all ${config.color}`}
              >
                <span className="w-6 text-center text-base">{config.icon}</span>
                
                <span className={`flex-1 ${isActive ? 'animate-pulse' : ''}`}>
                  {step.title}
                </span>

                {isActive && (
                  <motion.span
                    animate={{ opacity: [1, 0.4, 1] }}
                    transition={{ repeat: Infinity, duration: 1.5 }}
                    className="text-xs px-2 py-0.5 bg-violet-500/10 rounded-full"
                  >
                    running...
                  </motion.span>
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