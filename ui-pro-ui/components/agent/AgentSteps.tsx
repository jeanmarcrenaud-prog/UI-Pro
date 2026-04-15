'use client'

import { StepItem } from './index'
import type { AgentStep } from '@/lib/types'

export function AgentSteps({ steps }: { steps: AgentStep[] }) {
  if (!steps || steps.length === 0) return null

  // Map each step to our StepItem component
  return (
    <div className="space-y-1 mt-4">
      {steps.map((step) => (
        <StepItem key={step.id} step={step} />
      ))}
    </div>
  )
}
