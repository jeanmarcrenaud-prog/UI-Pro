'use client'

import type { AgentStep } from '@/lib/types'

interface StepItemProps {
  step: AgentStep
}

// Status icons mapping (flexible, extendable)
const statusConfig: Record<AgentStep['status'], { icon: string; color: string; label: string }> = {
  done: { icon: '✓', color: 'text-emerald-400', label: 'done' },
  active: { icon: '→', color: 'text-violet-400', label: 'active' },
  pending: { icon: '-', color: 'text-slate-500', label: 'pending' },
  error: { icon: '!', color: 'text-red-400', label: 'error' },
}

export function StepItem({ step }: StepItemProps) {
  const config = statusConfig[step.status] || statusConfig.pending
  
  return (
    <div className="pl-4 border-l-2 border-slate-800/50">
      <div className="flex items-center gap-2 text-sm">
        <span className={config.color}>
          {config.icon}
        </span>
        <span className="text-slate-300">{step.title}</span>
        {step.status === 'active' && (
          <span className="text-xs text-violet-400">({config.label})</span>
        )}
        {step.status === 'error' && (
          <span className="text-xs text-red-400">({config.label})</span>
        )}
      </div>
      {step.detail && (
        <div className="pl-4 text-xs text-slate-500 mt-0.5">
          {step.detail}
        </div>
      )}
    </div>
  )
}