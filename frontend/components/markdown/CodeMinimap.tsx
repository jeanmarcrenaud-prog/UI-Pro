// CodeMinimap.tsx
// Role: Canvas-based minimap with semantic syntax highlighting and
//       VSCode-style interactions (click, drag, wheel, hover cursor).

'use client'

import { useEffect, useRef, memo, useCallback, useMemo, useState } from 'react'

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
  const dragRef = useRef<{ pointerId: number; startY: number; startScrollTop: number } | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isOverIndicator, setIsOverIndicator] = useState(false)

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

    // Compute viewport indicator bounds once for both drawing and hit-testing
    const scrollTop = container.scrollTop
    const scrollHeight = container.scrollHeight
    const clientHeight = container.clientHeight
    const hasOverflow = scrollHeight > clientHeight
    const indicatorHeight = hasOverflow
      ? Math.max(18, (clientHeight / scrollHeight) * canvas.height)
      : 0
    const indicatorTop = hasOverflow
      ? (scrollTop / scrollHeight) * canvas.height
      : 0

    // Dim overlay for the non-visible portion of the code
    if (hasOverflow) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.28)'
      ctx.fillRect(0, 0, canvas.width, indicatorTop)
      ctx.fillRect(
        0,
        indicatorTop + indicatorHeight,
        canvas.width,
        canvas.height - (indicatorTop + indicatorHeight),
      )
    }

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

    // Viewport indicator (translucent, with subtle border for visibility)
    if (hasOverflow) {
      const fill = isDragging
        ? 'rgba(167, 139, 250, 0.95)'
        : isOverIndicator
          ? 'rgba(167, 139, 250, 0.85)'
          : 'rgba(167, 139, 250, 0.7)'
      ctx.fillStyle = fill
      ctx.fillRect(0, indicatorTop, width, indicatorHeight)

      // Subtle 1px border on left/right to make edges visible against code
      ctx.fillStyle = 'rgba(255, 255, 255, 0.12)'
      ctx.fillRect(0, indicatorTop, 1, indicatorHeight)
      ctx.fillRect(width - 1, indicatorTop, 1, indicatorHeight)
    }
  }, [lines, totalLines, width, containerRef, isDragging, isOverIndicator])

  // Redraw when code changes
  useEffect(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(draw)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [draw])

  // Scroll listener — redraw on container scroll
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const onScroll = () => requestAnimationFrame(draw)

    container.addEventListener('scroll', onScroll, { passive: true })
    return () => container.removeEventListener('scroll', onScroll)
  }, [draw, containerRef])

  // Compute indicator bounds in canvas pixels (used for hit-testing)
  const getIndicatorPixelBounds = useCallback(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return null
    const scrollHeight = container.scrollHeight
    const clientHeight = container.clientHeight
    if (scrollHeight <= clientHeight) return null
    return {
      top: (container.scrollTop / scrollHeight) * canvas.height,
      height: Math.max(18, (clientHeight / scrollHeight) * canvas.height),
      canvasHeight: canvas.height,
    }
  }, [containerRef])

  // Pointer interaction: click anywhere to scroll, click+drag to pan viewport
  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return
    e.preventDefault()
    canvas.setPointerCapture(e.pointerId)

    const rect = canvas.getBoundingClientRect()
    const clickPercent = (e.clientY - rect.top) / rect.height
    // Center the viewport on the click point (more natural feel than scrolling to top of click)
    const targetScrollTop =
      clickPercent * container.scrollHeight - container.clientHeight / 2
    container.scrollTop = Math.max(
      0,
      Math.min(targetScrollTop, container.scrollHeight - container.clientHeight),
    )

    dragRef.current = {
      pointerId: e.pointerId,
      startY: e.clientY,
      startScrollTop: container.scrollTop,
    }
    setIsDragging(true)
  }

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    // Update hover state for cursor feedback
    const rect = canvas.getBoundingClientRect()
    const y = e.clientY - rect.top
    const bounds = getIndicatorPixelBounds()
    const overIndicator = bounds
      ? y >= bounds.top && y <= bounds.top + bounds.height
      : false
    if (overIndicator !== isOverIndicator) {
      setIsOverIndicator(overIndicator)
    }

    // Drag handling
    const drag = dragRef.current
    if (!drag || drag.pointerId !== e.pointerId) return
    const deltaY = e.clientY - drag.startY
    const scrollDelta = (deltaY / rect.height) * container.scrollHeight
    container.scrollTop = Math.max(
      0,
      Math.min(
        drag.startScrollTop + scrollDelta,
        container.scrollHeight - container.clientHeight,
      ),
    )
  }

  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const drag = dragRef.current
    if (drag && drag.pointerId === e.pointerId) {
      dragRef.current = null
      setIsDragging(false)
    }
    try {
      e.currentTarget.releasePointerCapture(e.pointerId)
    } catch {
      // pointer may already be released (e.g., on touch cancel)
    }
  }

  const handlePointerLeave = () => {
    setIsOverIndicator(false)
  }

  // Wheel scroll: scrolling over the minimap scrolls the editor
  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    const container = containerRef.current
    if (!container) return
    e.preventDefault()
    e.stopPropagation()
    container.scrollTop += e.deltaY
  }

  // Cursor: grabbing while dragging, grab when over indicator, pointer otherwise
  const cursorClass = isDragging
    ? 'cursor-grabbing'
    : isOverIndicator
      ? 'cursor-grab'
      : 'cursor-pointer'

  return (
    <div className={`absolute right-0 top-0 bottom-0 bg-[#0a0f1a] border-l border-slate-700 overflow-hidden ${className}`}>
      <canvas
        ref={canvasRef}
        className={`${cursorClass} hover:brightness-105 active:brightness-90 transition-all`}
        width={width}
        height={520}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        onWheel={handleWheel}
      />
    </div>
  )
})
