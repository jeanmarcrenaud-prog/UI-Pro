'use client'

import React from 'react'

export interface StepItemProps {
  step: {
    status: 'pending' | 'active' | 'done'
    title: string
    detail?: string
  }
  isLoading?: boolean
}

const statusIcons: Record<string, string> = {
  done: '✅',
  active: '⚙️',
  pending: '⏳',
}

const statusTexts: Record<string, string> = {
  done: '✓',
  active: '→',
  pending: '-',
}

export function StepItem({ step }: StepItemProps) {
  return (
    <div className="pl-4 border-l-2 border-slate-800/50">
      <div className="flex items-center gap-2 text-sm">
        <span>
          {statusIcons[step.status]}
        </span>
        <span className="text-slate-300">{step.title}</span>
        {step.status === 'active' && (
          <span className="text-xs text-violet-400">(active)</span>
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
