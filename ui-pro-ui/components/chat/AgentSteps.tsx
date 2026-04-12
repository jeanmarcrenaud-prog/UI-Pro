'use client'

// components/agent/AgentSteps.tsx

type Step = {
  id: string
  title: string
  status: "pending" | "active" | "done"
}

export default function AgentSteps({ steps }: { steps: Step[] }) {
  return (
    <div className="bg-[#1e293b] p-4 rounded-xl shadow w-fit">
      <div className="text-sm text-gray-400 mb-2">⚡ Iteration 1</div>

      {steps.map((step) => (
        <div key={step.id} className="flex items-center gap-2 text-sm mb-1">
          {step.status === "done" && <span className="text-green-400">✔</span>}
          {step.status === "active" && (
            <span className="animate-spin text-blue-400">⚙</span>
          )}
          {step.status === "pending" && <span className="text-gray-500">⏳</span>}

          <span
            className={
              step.status === "done"
                ? "text-green-300"
                : step.status === "active"
                ? "text-blue-300"
                : "text-gray-400"
            }
          >
            {step.title}
          </span>
        </div>
      ))}
    </div>
  )
}