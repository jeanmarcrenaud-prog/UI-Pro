// CodeMinimap.tsx
// Role: Fixed minimap that stays visible while scrolling

'use client'

import { useCallback, memo, useMemo, useState, useEffect, useRef } from 'react'

interface CodeMinimapProps {
  code: string
  containerRef?: React.RefObject<HTMLDivElement | null>
}

export const CodeMinimap = memo(function CodeMinimap({ code, containerRef }: CodeMinimapProps) {
  const localRef = useRef<HTMLDivElement>(null)
  const [scrollRatio, setScrollRatio] = useState(0)
  
  // Get container - prefer prop ref, fallback to local
  const getContainer = useCallback(() => {
    return containerRef?.current || localRef.current?.parentElement?.querySelector('.overflow-y-auto')
  }, [containerRef])
  
  // Always call hooks first
  const lines = useMemo(() => code.split('\n').filter(l => l.trim()), [code])
  const totalLines = lines.length
  const shouldRender = totalLines >= 15
  
  // Track scroll
  useEffect(() => {
    const container = getContainer()
    if (!container || !shouldRender) return
    
    const handleScroll = () => {
      const maxScroll = container.scrollHeight - container.clientHeight
      const ratio = maxScroll > 0 ? container.scrollTop / maxScroll : 0
      setScrollRatio(Math.max(0, Math.min(1, ratio)))
    }
    
    handleScroll()
    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
  }, [getContainer, shouldRender])
  
const handleClick = useCallback((e: React.MouseEvent) => {
    const container = getContainer()
    if (!container) return
    
    const minimapRect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientY - minimapRect.top) / minimapRect.height))
    const targetScroll = ratio * (container.scrollHeight - container.clientHeight)
    
    container.scrollTo({ top: targetScroll, behavior: 'smooth' })
  }, [getContainer])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const container = getContainer()
    if (!container) return
    
    const startY = e.clientY
    const startScrollTop = container.scrollTop
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaY = moveEvent.clientY - startY
      const containerHeight = container.clientHeight
      const containerScrollHeight = container.scrollHeight
      const maxScroll = containerScrollHeight - containerHeight
      
      if (maxScroll <= 0) return
      
      // Convert pixel delta to scroll ratio
      const scrollDelta = (deltaY / containerHeight) * maxScroll
      container.scrollTop = Math.max(0, Math.min(maxScroll, startScrollTop + scrollDelta))
    }
    
    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
    
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [getContainer])

  if (!shouldRender) return null

  return (
    <div 
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      className="w-full h-full bg-slate-950/90 border-l border-slate-800 cursor-pointer select-none hover:bg-slate-900 transition-colors"
      title="Click or drag to navigate"
    >
      {/* Code lines */}
      <div className="w-full h-full overflow-hidden opacity-50">
        {lines.slice(0, 80).map((line, i) => (
          <div 
            key={i}
            className="w-full"
            style={{ 
              height: `${100 / Math.min(lines.length, 80)}%`,
              backgroundColor: line.trim() ? '#94a3b8' : 'transparent'
            }}
          />
        ))}
      </div>
      
      {/* Viewport indicator */}
      <div 
        className="absolute left-0 right-0 bg-violet-500/40 border border-violet-400/60 pointer-events-none"
        style={{
          top: `${scrollRatio * 100}%`,
          height: `${Math.min(100, (20 / lines.length) * 100)}%`,
        }}
      />
    </div>
  )
})