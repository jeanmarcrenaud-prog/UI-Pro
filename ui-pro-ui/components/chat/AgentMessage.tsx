// components/chat/AgentMessage.tsx
import AgentSteps from "../agent/AgentSteps"

export default function AgentMessage({ steps }) {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-purple-500 flex items-center justify-center">
        🤖
      </div>

      <AgentSteps steps={steps} />
    </div>
  )
}
