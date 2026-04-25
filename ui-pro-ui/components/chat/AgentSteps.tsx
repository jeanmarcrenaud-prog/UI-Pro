// AgentSteps.tsx (chat/)
// Role: Renders agent execution steps with status icons (pending/active/done) and progress animation

'use client'

import { motion } from 'framer-motion'

interface Step {
  id: string
  title: string
  status: 'pending' | 'active' | 'done'
}

interface AgentStepsProps {
  steps: Step[]
}

export function AgentSteps({ steps }: AgentStepsProps) {
  return (
    <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-4 max-w-lg mx-auto">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">🤖</span>
        <span className="text-sm font-medium text-white">Agent Working</span>
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="ml-auto text-xs"
        >
          ⚡
        </motion.span>
      </div>

      <div className="space-y-2">
        {steps.map((step) => (
          <div
            key={step.id}
            className={`flex items-center gap-3 text-sm ${
              step.status === 'done'
                ? 'text-green-400'
                : step.status === 'active'
                ? 'text-blue-400'
                : 'text-slate-500'
            }`}
          >
            {/* Step icon */}
            <span className="w-6 text-center">
              {step.status === 'done' ? '✅' : step.status === 'active' ? '⚙️' : '⏳'}
            </span>

            {/* Step name */}
            <span
              className={step.status === 'active' ? 'animate-pulse' : ''}
            >
              {step.title}
            </span>

            {/* Status indicator */}
            {step.status === 'active' && (
              <motion.span
                initial={{ width: 0 }}
                animate={{ width: 'auto' }}
                className="ml-auto text-xs bg-blue-500/20 px-2 py-0.5 rounded-full"
              >
                running...
              </motion.span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
