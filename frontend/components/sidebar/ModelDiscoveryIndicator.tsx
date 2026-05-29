// sidebar/ModelDiscoveryIndicator.tsx
// Role: Loading state indicator for model discovery

'use client'

import { motion } from 'framer-motion'
import { useI18n } from '@/lib/i18n'

export function ModelDiscoveryIndicator() {
  const { t } = useI18n()
  return (
    <div
      className="
        w-full 
        bg-slate-800/80 
        border border-slate-700/60 
        text-slate-400 
        text-xs 
        rounded-xl 
        px-3 py-2.5 
        flex items-center 
        justify-between
        gap-1.5
      "
      role="status"
      aria-live="polite"
    >
      <motion.span
        animate={{ rotate: 360 }}
        transition={{
          repeat: Infinity,
          duration: 1,
          ease: 'linear'
        }}
        className="w-3 h-3 border border-slate-400 border-t-transparent rounded-full"
      />
      <span className="flex items-center gap-1.5">
        {t.sidebar.discoverModels}
        <motion.span
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{
            repeat: Infinity,
            duration: 1.4,
            repeatDelay: 0.2
          }}
          className="text-slate-600 text-[10px]"
        >
          ↻
        </motion.span>
      </span>
    </div>
  )
}
