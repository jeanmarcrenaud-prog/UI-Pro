// components/chat/StreamingTokenGraph.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'

const MAX_POINTS = 20 // Number of bars to show
const UPDATE_INTERVAL = 500 // ms between updates

export function StreamingTokenGraph() {
  const tokenCount = useChatStore((s) => s.tokenCount)
  const [tokensPerSecond, setTokensPerSecond] = useState<number[]>([])
  const lastTokenCount = useRef(0)
  const lastUpdateTime = useRef(Date.now())

  useEffect(() => {
    const now = Date.now()
    const elapsed = (now - lastUpdateTime.current) / 1000 // seconds
    
    if (elapsed > 0) {
      const tokensInInterval = tokenCount - lastTokenCount.current
      const tps = Math.round(tokensInInterval / elapsed)
      
      setTokensPerSecond((prev) => {
        const newPoints = [...prev, tps]
        if (newPoints.length > MAX_POINTS) {
          return newPoints.slice(-MAX_POINTS)
        }
        return newPoints
      })
    }
    
    lastTokenCount.current = tokenCount
    lastUpdateTime.current = now
  }, [tokenCount])

  // Reset when streaming stops
  useEffect(() => {
    if (tokenCount === 0) {
      setTokensPerSecond([])
      lastTokenCount.current = 0
      lastUpdateTime.current = Date.now()
    }
  }, [tokenCount])

  if (tokensPerSecond.length === 0) {
    return null
  }

  const maxTps = Math.max(...tokensPerSecond, 1)
  const currentTps = tokensPerSecond[tokensPerSecond.length - 1] || 0

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/50 rounded-lg">
      {/* Mini bar graph */}
      <div className="flex items-end gap-0.5 h-6 w-24">
        {tokensPerSecond.map((tps, i) => {
          const height = Math.max((tps / maxTps) * 100, 10)
          const isLast = i === tokensPerSecond.length - 1
          return (
            <div
              key={i}
              className={`w-1 rounded-sm transition-all duration-200 ${
                isLast 
                  ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]' 
                  : 'bg-emerald-600/60'
              }`}
              style={{ height: `${height}%` }}
            />
          )
        })}
      </div>
      
      {/* Current TPS display */}
      <div className="text-[10px] font-mono">
        <span className="text-emerald-400">{currentTps}</span>
        <span className="text-slate-500"> t/s</span>
      </div>
      
      {/* Total tokens */}
      <div className="text-[10px] font-mono text-slate-500">
        {tokenCount} tok
      </div>
    </div>
  )
}