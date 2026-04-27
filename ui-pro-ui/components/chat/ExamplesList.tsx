// ExamplesList.tsx
// Role: Example prompts displayed on empty chat

'use client'

import { motion } from 'framer-motion'

interface Example {
  icon: string
  text: string
  prompt: string
}

interface ExamplesListProps {
  examples: Example[]
  onSelect: (prompt: string) => void
  disabled?: boolean
}

export function ExamplesList({ examples, onSelect, disabled }: ExamplesListProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center text-slate-400 mt-8"
    >
      <div className="text-6xl mb-4">👋</div>
      <h2 className="text-xl font-semibold">Welcome to UI-Pro</h2>
      <p className="text-sm mt-1">AI Agent System</p>

      <div className="mt-8 max-w-md mx-auto space-y-2">
        {examples.map((ex) => (
          <button
            key={ex.prompt}
            onClick={() => onSelect(ex.prompt)}
            disabled={disabled}
            className="w-full text-left p-3 bg-slate-900/50 hover:bg-slate-900 border border-slate-700 hover:border-violet-500 rounded-lg text-sm transition disabled:opacity-50"
          >
            <span className="mr-2">{ex.icon}</span>
            {ex.text}
          </button>
        ))}
      </div>
    </motion.div>
  )
}