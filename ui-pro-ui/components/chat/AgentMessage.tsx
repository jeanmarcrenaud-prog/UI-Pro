// components/chat/AgentMessage.tsx
import { AgentSteps } from '../agent/AgentSteps'
import type { AgentStep } from '@/lib/types'

export default function AgentMessage({ steps }: { steps: AgentStep[] }) {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs">
        🤖
      </div>

      <AgentSteps steps={steps} />
    </div>
  )
}
