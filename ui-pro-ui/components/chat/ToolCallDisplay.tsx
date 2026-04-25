// ToolCallDisplay.tsx
// Role: Displays active tool call badges (e.g., "execute", "read_file") with running/completed status
// Listens to events toolCall for real-time updates

'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { events } from '@/lib/events'

interface ToolCall {
  tool: string
  status: 'start' | 'done'
  result?: string
}

export function ToolCallDisplay() {
  const [activeTools, setActiveTools] = useState<ToolCall[]>([])

  useEffect(() => {
    const handleToolCall = (data: { tool: string; status: 'start' | 'done' }) => {
      if (data.status === 'start') {
        setActiveTools(prev => [...prev, { tool: data.tool, status: 'start' }])
      } else {
        setActiveTools(prev => 
          prev.map(t => t.tool === data.tool ? { ...t, status: 'done' } : t)
        )
      }
    }

    events.on('toolCall', handleToolCall)
    
    return () => {
      events.off('toolCall', handleToolCall)
    }
  }, [])

  if (activeTools.length === 0) return null

  return (
    <div className="flex gap-2 flex-wrap justify-center py-2">
      <AnimatePresence>
        {activeTools.map((tool, index) => (
          <motion.div
            key={`${tool.tool}-${index}`}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            className={`px-3 py-1 rounded-full text-xs flex items-center gap-1 ${
              tool.status === 'done'
                ? 'bg-green-900/50 text-green-400'
                : 'bg-orange-900/50 text-orange-400'
            }`}
          >
            {tool.status === 'done' ? '✓' : '⚡'}
            <span>{tool.tool}</span>
            {tool.status === 'start' && (
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1 }}
              />
            )}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}