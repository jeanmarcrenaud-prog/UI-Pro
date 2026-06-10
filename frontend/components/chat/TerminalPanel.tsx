// TerminalPanel.tsx (chat/)
// Role: Terminal output display for execution streaming - shows stdout/stderr lines
// from the subprocess in real-time with monospace formatting and collapse/expand

'use client'

import { useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Terminal, X, ChevronDown, ChevronUp } from 'lucide-react'

export interface TerminalOutputLine {
  content: string
  channel: string  // 'stdout' | 'stderr'
  timestamp?: number
}

interface TerminalPanelProps {
  lines: TerminalOutputLine[]
  isVisible: boolean
  onToggleVisibility: () => void
  onClear: () => void
}

const MAX_VISIBLE_LINES = 1000

export function TerminalPanel({
  lines,
  isVisible,
  onToggleVisibility,
  onClear,
}: TerminalPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const autoScrollRef = useRef(true)

  // Auto-scroll to bottom when new lines arrive
  useEffect(() => {
    if (autoScrollRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [lines.length])

  // Detect manual scroll to disable auto-scroll
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return
    const el = scrollRef.current
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    autoScrollRef.current = isAtBottom
  }, [])

  const displayLines = lines.slice(-MAX_VISIBLE_LINES)

  return (
    <div className="border-t border-[var(--border-subtle)]">
      {/* Header */}
      <button
        onClick={onToggleVisibility}
        className="w-full flex items-center gap-2 px-6 py-2.5 bg-[var(--surface-primary)] hover:bg-[var(--surface-secondary)] transition-colors cursor-pointer"
      >
        <Terminal className="w-4 h-4 text-emerald-400 shrink-0" />
        <span className="text-sm font-medium text-[var(--text-secondary)]">Terminal</span>
        <span className="text-xs text-[var(--text-muted)] font-mono">
          {lines.length} line{lines.length !== 1 ? 's' : ''}
        </span>

        <div className="flex-1" />

        {lines.length > 0 && isVisible && (
          <span
            onClick={(e) => {
              e.stopPropagation()
              onClear()
            }}
            className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-red-400 transition-colors px-2 py-0.5 rounded hover:bg-red-500/10"
          >
            <X className="w-3 h-3" />
            Clear
          </span>
        )}

        <span className="text-[var(--text-muted)]">
          {isVisible ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronUp className="w-4 h-4" />
          )}
        </span>
      </button>

      {/* Terminal Output */}
      <AnimatePresence>
        {isVisible && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div
              ref={scrollRef}
              onScroll={handleScroll}
              className="max-h-[300px] overflow-y-auto bg-slate-950 border-t border-[var(--border-subtle)]"
            >
              {displayLines.length === 0 ? (
                <div className="px-6 py-8 text-center text-sm text-[var(--text-muted)] font-mono">
                  Waiting for execution output...
                </div>
              ) : (
                <div className="p-4 space-y-0.5 font-mono text-sm leading-relaxed">
                  {displayLines.map((line, i) => (
                    <div
                      key={i}
                      className={`whitespace-pre-wrap break-all ${
                        line.channel === 'stderr'
                          ? 'text-red-400'
                          : 'text-slate-300'
                      }`}
                    >
                      {line.content}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
