// components/agent/AgentCanvas.tsx
// Agent Canvas: ReactFlow-based visual LangGraph pipeline with real-time node status
'use client'

import { useMemo } from 'react'
import { useAgentStore } from '@/lib/stores/agentStore'
import { useChatStore } from '@/lib/stores/chatStore'
import GraphVisualization from '@/components/canvas/GraphVisualization'
import type { CanvasStep } from '@/lib/stores/agentCanvasStore'

interface AgentCanvasProps {
  className?: string
}

const STEP_TO_CANVAS: Record<string, string> = {
  'step-analyzing':  'Analyze',
  'step-planning':   'Plan',
  'step-coding':     'Code',
  'step-reviewing':  'Review',
  'step-executing':  'Execute',
}

const STEP_ORDER = ['step-analyzing', 'step-planning', 'step-coding', 'step-reviewing', 'step-executing']

export function AgentCanvas({ className = '' }: AgentCanvasProps) {
  const agentSteps = useAgentStore((s) => s.steps)
  const isStreaming = useChatStore((s) => s.isLoading)

  const canvasSteps: CanvasStep[] = useMemo(() => {
    const map = new Map<string, CanvasStep>()

    for (const id of STEP_ORDER) {
      const name = STEP_TO_CANVAS[id] ?? id
      map.set(id, { name, status: 'pending' })
    }

    for (const step of agentSteps) {
      if (!STEP_ORDER.includes(step.id)) continue
      const entry = map.get(step.id)
      if (!entry) continue

      entry.status = step.status === 'done' ? 'done'
        : step.status === 'error' ? 'error'
        : 'running'

      if (step.duration) entry.durationMs = step.duration * 1000
      if (step.tokens) entry.tokens = step.tokens
    }

    // Fix loop node (appended when active)
    const hasFixing = agentSteps.some((s) => s.id === 'step-fixing' || s.id === 'step-fix_code')
    if (hasFixing) {
      const fixStep = agentSteps.find((s) => s.id === 'step-fixing' || s.id === 'step-fix_code')
      const isActive = fixStep?.status === 'active'
      map.set('step-fix_code', {
        name: 'Fix Code',
        status: isActive ? 'running' : 'done',
        durationMs: fixStep?.duration ? fixStep.duration * 1000 : undefined,
        tokens: fixStep?.tokens,
        attempt: fixStep?.attempt,
        maxAttempts: fixStep?.maxAttempts,
      })
    }

    return Array.from(map.values())
  }, [agentSteps])

  return (
    <div className={`bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-violet-500/30 rounded-2xl shadow-lg shadow-violet-500/10 ${className}`}>
      <div className="h-[600px]">
        <GraphVisualization steps={canvasSteps} />
      </div>
      {isStreaming && (
        <div className="flex items-center gap-1.5 px-4 pb-3 -mt-2">
          <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
          <span className="text-[10px] text-slate-500 font-mono">streaming</span>
        </div>
      )}
    </div>
  )
}
