// CodeMinimap.tsx
// Role: Canvas-based minimap with semantic syntax highlighting

'use client'

import { useEffect, useRef, memo, useCallback, useMemo } from 'react'

interface CodeMinimapProps {
  code: string
  containerRef: React.RefObject<HTMLDivElement>
  width?: number
  className?: string
}

export const CodeMinimap = memo(function CodeMinimap({
  code,
  containerRef,
  width = 56,
  className = ''
}: CodeMinimapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number | null>(null)

  // Memoized lines for performance
  const lines = useMemo(() => code.split('\n'), [code])
  const totalLines = lines.length

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || totalLines === 0) return

    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return

    const container = containerRef.current
    if (!container) return

    canvas.width = width
    canvas.height = container.clientHeight || 520

    const lineHeight = canvas.height / Math.max(totalLines, 60)

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw each line with semantic coloring
    for (let i = 0; i < totalLines; i++) {
      const line = lines[i]
      const y = i * lineHeight
      const trimmed = line.trim()

      let intensity = 0.12
      let hue = 210 // default

      // Semantic coloring
      if (trimmed.startsWith('def ') || trimmed.startsWith('class ')) {
        hue = 270
        intensity = 0.9
      } else if (trimmed.startsWith('import ') || trimmed.startsWith('from ')) {
        hue = 160
        intensity = 0.75
      } else if (trimmed.startsWith('#')) {
        hue = 35
        intensity = 0.4
      } else if (trimmed.includes('return ') || trimmed.includes('if ') || trimmed.includes('else')) {
        hue = 200
        intensity = 0.65
      } else if (line.length > 70) {
        intensity = 0.8
      }

      ctx.fillStyle = `hsla(${hue}, 88%, 68%, ${intensity})`
      ctx.fillRect(3, Math.floor(y), width - 7, Math.max(1.2, lineHeight - 0.8))
    }

    // Viewport indicator
    const scrollTop = container.scrollTop
    const scrollHeight = container.scrollHeight
    const clientHeight = container.clientHeight

    if (scrollHeight > clientHeight) {
      const indicatorHeight = (clientHeight / scrollHeight) * canvas.height
      const indicatorTop = (scrollTop / scrollHeight) * canvas.height

      ctx.fillStyle = 'rgba(167, 139, 250, 0.85)'
      ctx.fillRect(0, indicatorTop, width, Math.max(18, indicatorHeight))
    }
  }, [lines, totalLines, width, containerRef])

  // Redraw when code changes or scroll happens
  useEffect(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(draw)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [draw])

  // Scroll listener
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const onScroll = () => requestAnimationFrame(draw)

    container.addEventListener('scroll', onScroll, { passive: true })
    return () => container.removeEventListener('scroll', onScroll)
  }, [draw, containerRef])

  return (
    <div className={`absolute right-0 top-0 bottom-0 bg-[#0a0f1a] border-l border-slate-700 overflow-hidden ${className}`}>
      <canvas
        ref={canvasRef}
        className="cursor-pointer hover:brightness-105 active:brightness-90 transition-all"
        width={width}
        height={520}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect()
          const clickPercent = (e.clientY - rect.top) / rect.height

          if (containerRef.current) {
            containerRef.current.scrollTop = 
              clickPercent * containerRef.current.scrollHeight
          }
        }}
      />
    </div>
  )
})