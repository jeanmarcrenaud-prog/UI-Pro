// components/chat/StreamingTokenGraph.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'

const MAX_POINTS = 20 // Number of bars to show
const UPDATE_INTERVAL = 500 // ms between updates
const ETA_MIN_TOKENS = 30 // Minimum tokens before showing ETA
const ETA_MIN_SECONDS = 5 // Minimum seconds before showing ETA

function formatEta(seconds: number): string {
  if (seconds < 60) {
    return `~${Math.round(seconds)}s`
  }
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return secs > 0 ? `~${mins}m ${secs}s` : `~${mins}m`
}

export function StreamingTokenGraph() {
  const tokenCount = useChatStore((s) => s.tokenCount)
  const [tokensPerSecond, setTokensPerSecond] = useState<number[]>([])
  const [eta, setEta] = useState<string | null>(null)
  const [isComplete, setIsComplete] = useState(false)
  const lastTokenCount = useRef(0)
  const lastUpdateTime = useRef(Date.now())
  const streamStartTime = useRef<number | null>(null)
  const totalElapsed = useRef(0)

  // Reset when streaming stops
  useEffect(() => {
    if (tokenCount === 0) {
      setTokensPerSecond([])
      setEta(null)
      setIsComplete(false)
      lastTokenCount.current = 0
      lastUpdateTime.current = Date.now()
      streamStartTime.current = null
      totalElapsed.current = 0
    }
  }, [tokenCount])

  // Update TPS and ETA
  useEffect(() => {
    const now = Date.now()
    const elapsed = (now - lastUpdateTime.current) / 1000 // seconds

    if (elapsed > 0) {
      const tokensInInterval = tokenCount - lastTokenCount.current
      const tps = Math.round(tokensInInterval / elapsed)

      // Track stream start for ETA calculation
      if (streamStartTime.current === null && tokenCount > 0) {
        streamStartTime.current = now
      }

      setTokensPerSecond((prev) => {
        const newPoints = [...prev, tps]
        if (newPoints.length > MAX_POINTS) {
          return newPoints.slice(-MAX_POINTS)
        }
        return newPoints
      })

      // Calculate ETA
      if (tokenCount > ETA_MIN_TOKENS && streamStartTime.current !== null) {
        const totalElapsedSeconds = (now - streamStartTime.current) / 1000
        if (totalElapsedSeconds > ETA_MIN_SECONDS) {
          const avgTps = tokenCount / totalElapsedSeconds
          if (avgTps > 1) {
            // Estimate: assume we're ~65% through based on typical LLM response patterns
            // (thinking/reasoning first, then code output)
            const estimatedTotal = tokenCount / 0.65
            const remaining = estimatedTotal - tokenCount
            const etaSeconds = remaining / avgTps
            setEta(formatEta(etaSeconds))
            setIsComplete(false)
          }
        }
      }
    }

    lastTokenCount.current = tokenCount
    lastUpdateTime.current = now
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

      {/* ETA or completion */}
      {eta && !isComplete && (
        <div className="text-[10px] font-mono text-amber-400">
          {eta}
        </div>
      )}

      {/* Total tokens */}
      <div className="text-[10px] font-mono text-slate-500">
        {tokenCount} tok
      </div>
    </div>
  )
}