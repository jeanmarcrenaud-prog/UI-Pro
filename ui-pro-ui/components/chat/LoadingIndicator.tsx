// LoadingIndicator.tsx
// Role: Animated dots showing loading state

'use client'

import { motion } from 'framer-motion'

interface LoadingIndicatorProps {
  label?: string
}

export function LoadingIndicator({ label = 'Loading' }: LoadingIndicatorProps) {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs">
        🤖
      </div>

      <div className="bg-slate-800 rounded-2xl px-4 py-3 flex gap-2 items-center">
        {[0, 0.15, 0.3].map((d, i) => (
          <motion.span
            key={i}
            animate={{ y: [0, -4, 0] }}
            transition={{ repeat: Infinity, duration: 0.6, delay: d }}
            className="w-2 h-2 bg-slate-400 rounded-full"
          />
        ))}
        {label && (
          <span className="text-sm text-slate-400 ml-1">{label}</span>
        )}
      </div>
    </div>
  )
}