// components/VirtualizedLogs.tsx
// Role: Virtualized log viewer - renders only visible logs to prevent performance issues
// with large log buffers. Uses simple height-based virtualization.

'use client'

import { useMemo, useRef, useEffect } from 'react'

interface VirtualizedLogsProps {
  logs: string[]
  lineHeight?: number
  containerHeight?: number
}

export function VirtualizedLogs({
  logs,
  lineHeight = 18,
  containerHeight = 400,
}: VirtualizedLogsProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Calculate visible range
  const visibleRange = useMemo(() => {
    if (!containerRef.current) return { start: 0, end: logs.length }

    const scrollTop = containerRef.current.scrollTop
    const start = Math.max(0, Math.floor(scrollTop / lineHeight) - 5)
    const end = Math.min(logs.length, Math.ceil((scrollTop + containerHeight) / lineHeight) + 5)

    return { start, end }
  }, [logs.length, lineHeight, containerHeight])

  // Auto-scroll to bottom when new logs added
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs.length])

  const visibleLogs = logs.slice(visibleRange.start, visibleRange.end)
  const totalHeight = logs.length * lineHeight
  const offsetTop = visibleRange.start * lineHeight

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto bg-slate-950/50"
      style={{ height: containerHeight }}
      onScroll={() => {
        // Trigger re-render when scrolling
        containerRef.current?.scrollTop
      }}
    >
      {logs.length === 0 ? (
        <div className="p-4 text-slate-600 italic text-[10px]">
          Waiting for execution...
        </div>
      ) : (
        <div style={{ height: totalHeight, position: 'relative' }}>
          {/* Offset visible logs to correct position */}
          <div
            style={{
              transform: `translateY(${offsetTop}px)`,
              willChange: 'transform',
            }}
          >
            {visibleLogs.map((log, idx) => (
              <div
                key={visibleRange.start + idx}
                className="py-0.5 px-4 font-mono text-[10px] break-all text-slate-300"
                style={{ height: lineHeight }}
              >
                {log}
              </div>
            ))}
          </div>

          {/* Scroll anchor */}
          <div ref={scrollRef} />
        </div>
      )}
    </div>
  )
}
