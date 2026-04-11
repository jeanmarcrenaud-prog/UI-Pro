'use client'

// AgentSteps - Displays agent reasoning steps inline
import type { AgentStep } from '@/lib/types'

interface AgentStepsProps {
  steps: AgentStep[]
}

export function AgentSteps({ steps }: AgentStepsProps) {
  if (!steps.length) return null

  return (
    <div className="w-full rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
      <h4 className="mb-2 text-sm font-medium text-gray-600 dark:text-gray-400">
        🤖 Agent Steps
      </h4>
      <ol className="space-y-1">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`flex items-center gap-2 text-sm ${
              step.status === 'done'
                ? 'text-green-600 dark:text-green-400'
                : step.status === 'active'
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-gray-400'
            }`}
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-gray-200 text-xs dark:bg-gray-700">
              {step.status === 'done' ? '✓' : index + 1}
            </span>
            <span className={step.status === 'active' ? 'animate-pulse' : ''}>
              {step.title}
            </span>
            {step.detail && (
              <span className="text-xs text-gray-500">— {step.detail}</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}