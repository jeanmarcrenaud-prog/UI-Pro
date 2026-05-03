// CodeMinimap.tsx
// Role: Canvas-based minimap with syntax highlighting and viewport

'use client'

import { useEffect, useRef, memo, useCallback } from 'react'

interface CodeMinimapProps {
  code: string
  containerRef: React.RefObject<HTMLDivElement>
  width?: number
  height?: number
  className?: string
}

export const CodeMinimap = memo(function CodeMinimap({
  code,
  containerRef,
  width = 56,
  height = '100%',
  className = ''
}: CodeMinimapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationFrameRef = useRef<number | null>(null)

  const drawMinimap = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !code) return

    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return

    const lines = code.split('\n')
    const totalLines = lines.length
    if (totalLines === 0) return

    // Set canvas dimensions
    canvas.width = width
    canvas.height = containerRef.current?.clientHeight || 520

    const lineHeight = canvas.height / Math.max(totalLines, 50) // Minimum visible lines

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw code density map
    for (let i = 0; i < totalLines; i++) {
      const line = lines[i]
      const y = i * lineHeight
      const lineLength = line.length

      // Intensity based on content density
      let intensity = 0.15 // base

      if (lineLength > 60) intensity = 0.75
      else if (lineLength > 30) intensity = 0.55
      else if (line.includes('def ') || line.includes('class ') || line.includes('import ')) 
        intensity = 0.85
      else if (line.includes('return ') || line.includes('if ') || line.includes('//')) 
        intensity = 0.45

      // Color based on content type
      let hue = 210 // default blue-ish
      if (line.includes('def ') || line.includes('class ')) hue = 280   // purple
      else if (line.includes('import ') || line.includes('from ')) hue = 160 // green
      else if (line.trim().startsWith('#')) hue = 40 // orange (comments)

      ctx.fillStyle = `hsla(${hue}, 85%, 65%, ${intensity})`
      ctx.fillRect(2, y, width - 6, Math.max(1, lineHeight - 1))
    }

    // Draw viewport indicator (current scroll position)
    if (containerRef.current) {
      const scrollTop = containerRef.current.scrollTop
      const scrollHeight = containerRef.current.scrollHeight
      const clientHeight = containerRef.current.clientHeight

      if (scrollHeight > clientHeight) {
        const indicatorHeight = (clientHeight / scrollHeight) * canvas.height
        const indicatorTop = (scrollTop / scrollHeight) * canvas.height

        ctx.fillStyle = 'rgba(167, 139, 250, 0.7)' // violet-400
        ctx.fillRect(0, indicatorTop, width, indicatorHeight)
      }
    }
  }, [code, width, containerRef])

  // Redraw on code change or scroll
  useEffect(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }

    animationFrameRef.current = requestAnimationFrame(drawMinimap)

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [drawMinimap])

  // Listen to scroll on container
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleScroll = () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = requestAnimationFrame(drawMinimap)
    }

    container.addEventListener('scroll', handleScroll, { passive: true })

    return () => {
      container.removeEventListener('scroll', handleScroll)
    }
  }, [drawMinimap, containerRef])

  return (
    <div className={`absolute right-0 top-0 bottom-0 bg-slate-950 border-l border-slate-700 ${className}`}>
      <canvas
        ref={canvasRef}
        className="cursor-pointer hover:brightness-110 transition-all"
        width={width}
        height={500}
        onClick={(e) => {
          // Click to scroll to position
          const rect = e.currentTarget.getBoundingClientRect()
          const clickY = e.clientY - rect.top
          const percentage = clickY / rect.height

          if (containerRef.current) {
            const scrollHeight = containerRef.current.scrollHeight
            containerRef.current.scrollTop = percentage * scrollHeight
          }
        }}
      />
    </div>
  )
})