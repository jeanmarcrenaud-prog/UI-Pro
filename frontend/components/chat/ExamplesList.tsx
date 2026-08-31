// ExamplesList.tsx
// Role: Example prompts displayed on empty chat — fun entrance with staggered cards,
//       animated gradient title, floating emoji and a confetti pop on selection.

'use client'

import { useCallback } from 'react'
import { motion, Variants } from 'framer-motion'
import confetti from 'canvas-confetti'

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

const containerVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.25 } },
}

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 18, scale: 0.96 },
  show: { opacity: 1, y: 0, scale: 1 },
}

function fireConfetti() {
  confetti({
    particleCount: 36,
    spread: 55,
    angle: 90,
    origin: { x: 0.5, y: 0.42 },
    colors: ['#8b5cf6', '#c084fc', '#f0abfc', '#a78bfa'],
    zIndex: 100,
  })
}

export function ExamplesList({ examples, onSelect, disabled }: ExamplesListProps) {
  const handleClick = useCallback(
    (ex: Example) => {
      if (!disabled) {
        fireConfetti()
      }
      onSelect(ex.prompt)
    },
    [onSelect, disabled]
  )

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="text-center text-slate-400 mt-8"
    >
      {/* Floating emoji */}
      <div className="mb-3">
        <motion.span
          className="inline-block text-6xl select-none"
          animate={{ y: [0, -8, 0], rotate: [-4, 4, -4] }}
          transition={{ duration: 3.2, repeat: Infinity, ease: 'easeInOut' }}
        >
          👋
        </motion.span>
      </div>

      {/* Gradient animated title */}
      <h2 className="text-2xl font-bold uipro-gradient-text">Welcome to UI-Pro</h2>
      <p className="text-sm mt-1 text-slate-500">AI Agent System — pick an example below ✨</p>

      {/* Staggered cards */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="mt-8 max-w-md mx-auto space-y-2.5"
      >
        {examples.map((ex) => (
          <motion.button
            key={ex.prompt}
            variants={cardVariants}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => handleClick(ex)}
            disabled={disabled}
            className="w-full text-left p-3 rounded-xl border border-slate-700 bg-[var(--surface-primary)]/60 hover:bg-[var(--surface-secondary)] hover:border-violet-500 hover:shadow-[0_0_18px_var(--accent-soft)] transition-colors duration-200 disabled:opacity-40 disabled:pointer-events-none"
          >
            <span className="mr-2 text-lg inline-block">{ex.icon}</span>
            {ex.text}
          </motion.button>
        ))}
      </motion.div>

      {/* Hint footer */}
      <p className="mt-6 text-xs text-slate-600">
        Tip : les exemples lancent une vraie tâche — et un mini-confetti 🎉
      </p>
    </motion.div>
  )
}
