// TerminalPanel.tsx (chat/)
// Role: Terminal output display for execution streaming - shows stdout/stderr lines
// from the subprocess in real-time with monospace formatting and collapse/expand

'use client'

import { useRef, useEffect, useCallback, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Terminal, X, ChevronDown, ChevronUp, Maximize2, Minimize2, ArrowDownToLine } from 'lucide-react'

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

// Common error/traceback patterns for syntax highlighting
const ERROR_PATTERNS = [
  { regex: /(Traceback \(most recent call last\))/g, className: 'text-red-300 font-semibold' },
  { regex: /(Error|ERROR|Error:|Exception|SyntaxError|TypeError|ValueError|KeyError|IndexError|AttributeError|ImportError|ModuleNotFoundError|FileNotFoundError|RuntimeError|NameError|ZeroDivisionError|KeyError|StopIteration):/g, className: 'text-red-400 font-bold' },
  { regex: /File "[^"]+", line \d+/g, className: 'text-yellow-400' },
  { regex: /at\s+\S+\s+\(.*\)/g, className: 'text-yellow-300' },
  { regex: /in\s+<module>/g, className: 'text-yellow-400' },
  { regex: /FAILED|FAIL|✗|✘/g, className: 'text-red-400 font-semibold' },
  { regex: /PASSED|PASS|✓|✔|ok\b/g, className: 'text-emerald-400 font-semibold' },
  { regex: /warning|WARNING|WARN/g, className: 'text-orange-400' },
  { regex: /npm ERR|npm WARN|npm error/g, className: 'text-red-400' },
  { regex: /SyntaxError: Unexpected token/g, className: 'text-red-400 font-bold bg-red-950/50' },
]

interface HighlightPart {
  text: string
  className: string
}

function highlightSyntax(line: string): JSX.Element {
  if (!line) return <></>

  let parts: HighlightPart[] = [{ text: line, className: '' }]

  for (const { regex, className } of ERROR_PATTERNS) {
    const newParts: typeof parts = []
    for (const part of parts) {
      if (part.className) {
        newParts.push(part)
        continue
      }
      let lastIndex = 0
      let match: RegExpExecArray | null
      const re = new RegExp(regex.source, 'g')
      while ((match = re.exec(part.text)) !== null) {
        if (match.index > lastIndex) {
          newParts.push({ text: part.text.slice(lastIndex, match.index), className: '' })
        }
        newParts.push({ text: match[0], className })
        lastIndex = match.index + match[0].length
      }
      if (lastIndex < part.text.length) {
        newParts.push({ text: part.text.slice(lastIndex), className: '' })
      }
    }
    parts = newParts
  }

  return (
    <>
      {parts.map((p, i) =>
        p.className ? (
          <span key={i} className={p.className}>{p.text}</span>
        ) : (
          <span key={i}>{p.text}</span>
        )
      )}
    </>
  )
}

export function TerminalPanel({
  lines,
  isVisible,
  onToggleVisibility,
  onClear,
}: TerminalPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const autoScrollRef = useRef(true)
  const [expanded, setExpanded] = useState(false)
  const [showScrollBtn, setShowScrollBtn] = useState(false)

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
    setShowScrollBtn(!isAtBottom && lines.length > 10)
  }, [lines.length])

  const scrollToBottom = useCallback(() => {
    if (!scrollRef.current) return
    scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    autoScrollRef.current = true
    setShowScrollBtn(false)
  }, [])

  const displayLines = lines.slice(-MAX_VISIBLE_LINES)
  const hasErrors = lines.some(l => l.channel === 'stderr')

  const maxHeight = expanded
    ? '80vh'
    : hasErrors
      ? 'min(45vh, 500px)'
      : 'min(30vh, 300px)'

  return (
    <div className="border-t border-[var(--border-subtle)]">
      {/* Header */}
      <button
        onClick={onToggleVisibility}
        className="w-full flex items-center gap-2 px-6 py-2.5 bg-[var(--surface-primary)] hover:bg-[var(--surface-secondary)] transition-colors cursor-pointer"
      >
        <Terminal className={`w-4 h-4 shrink-0 ${hasErrors ? 'text-red-400' : 'text-emerald-400'}`} />
        <span className="text-sm font-medium text-[var(--text-secondary)]">Terminal</span>
        <span className="text-xs text-[var(--text-muted)] font-mono">
          {lines.length} line{lines.length !== 1 ? 's' : ''}
        </span>

        {hasErrors && (
          <span className="text-[10px] font-medium text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded-full">
            {lines.filter(l => l.channel === 'stderr').length} error{(lines.filter(l => l.channel === 'stderr').length) !== 1 ? 's' : ''}
          </span>
        )}

        <div className="flex-1" />

        {lines.length > 0 && isVisible && (
          <>
            <span
              onClick={(e) => {
                e.stopPropagation()
                setExpanded(!expanded)
              }}
              className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-violet-400 transition-colors px-2 py-0.5 rounded hover:bg-violet-500/10"
            >
              {expanded ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
            </span>
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
          </>
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
              className="overflow-y-auto bg-slate-950 border-t border-[var(--border-subtle)] relative"
              style={{ maxHeight }}
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
                      className={`whitespace-pre-wrap break-all px-1.5 py-0.5 rounded ${
                        line.channel === 'stderr'
                          ? 'text-red-300 bg-red-950/20 border-l-2 border-red-500/40'
                          : 'text-slate-300 hover:bg-slate-900/50'
                      }`}
                    >
                      {line.channel === 'stderr' ? highlightSyntax(line.content) : line.content}
                    </div>
                  ))}
                </div>
              )}

              {/* Scroll-to-bottom floating button */}
              {showScrollBtn && (
                <button
                  onClick={scrollToBottom}
                  className="absolute bottom-3 right-3 p-2 rounded-full bg-slate-800 border border-slate-600 text-slate-400 hover:text-white hover:border-slate-500 transition-all shadow-lg"
                >
                  <ArrowDownToLine className="w-4 h-4" />
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
