// CodeMinimap.tsx
// Role: Fixed minimap that stays visible while scrolling

'use client'

import { useCallback, memo, useMemo, useState, useEffect } from 'react'

interface CodeMinimapProps {
  code: string
  containerRef?: React.RefObject<HTMLDivElement | null>
}

export const CodeMinimap = memo(function CodeMinimap({ code, containerRef }: CodeMinimapProps) {
  const containerEl = containerRef?.current
  const [scrollRatio, setScrollRatio] = useState(0)
  
  // Always call hooks first
  const lines = useMemo(() => code.split('\n').filter(l => l.trim()), [code])
  const totalLines = lines.length
  const shouldRender = totalLines >= 15
  
  // Track scroll
  useEffect(() => {
    if (!containerEl || !shouldRender) return
    
    const handleScroll = () => {
      const maxScroll = containerEl.scrollHeight - containerEl.clientHeight
      const ratio = maxScroll > 0 ? containerEl.scrollTop / maxScroll : 0
      setScrollRatio(Math.max(0, Math.min(1, ratio)))
    }
    
    handleScroll()
    containerEl.addEventListener('scroll', handleScroll, { passive: true })
    return () => containerEl.removeEventListener('scroll', handleScroll)
  }, [containerEl, shouldRender])
  
  const handleClick = useCallback((e: React.MouseEvent) => {
    if (!containerEl) return
    
    const rect = containerEl.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height))
    containerEl.scrollTo({ top: ratio * (containerEl.scrollHeight - containerEl.clientHeight), behavior: 'smooth' })
  }, [containerEl])

  if (!shouldRender) return null

  return (
    <div 
      onClick={handleClick}
      className="absolute right-0 top-0 bottom-0 w-14 bg-slate-950/90 border-l border-slate-800 cursor-pointer select-none z-10 hover:bg-slate-900 transition-colors"
      title="Click to navigate"
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