// SystemStats.tsx
// Role: Displays real-time system metrics - CPU, memory, GPU utilization and temperature via polling /health endpoint

'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'

interface SystemStats {
  cpu_percent: number | null
  memory_percent: number | null
  gpu?: {
    name: string
    utilization: number
    memory_used_mb: number
    memory_total_mb: number
    memory_percent: number
    temperature: number | null
  } | null
}

interface VUMeterProps {
  value: number
  label: string
  color?: 'cpu' | 'memory' | 'gpu'
  sublabel?: string
}

function VUMeter({ value, label, color = 'cpu', sublabel }: VUMeterProps) {
  const getColor = () => {
    switch (color) {
      case 'cpu':
        return 'from-blue-500 to-blue-600'
      case 'memory':
        return 'from-purple-500 to-purple-600'
      case 'gpu':
        return 'from-emerald-500 to-emerald-600'
    }
  }

  const getBgColor = () => {
    switch (color) {
      case 'cpu':
        return 'bg-blue-500/20'
      case 'memory':
        return 'bg-purple-500/20'
      case 'gpu':
        return 'bg-emerald-500/20'
    }
  }

  const getBarColor = () => {
    if (value >= 90) return 'bg-red-500'
    if (value >= 70) return 'bg-yellow-500'
    return `bg-gradient-to-r ${getColor()}`
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="text-slate-300 font-mono">
          {value !== null ? `${value.toFixed(1)}%` : 'N/A'}
        </span>
      </div>
      <div className={`h-2 ${getBgColor()} rounded-full overflow-hidden`}>
        <motion.div
          className={`h-full ${getBarColor()} rounded-full`}
          initial={{ width: 0 }}
          animate={{ width: `${value ?? 0}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
      {sublabel && (
        <p className="text-xs text-slate-500">{sublabel}</p>
      )}
    </div>
  )
}

function MemoryGauge({ used, total, percent }: { used: number; total: number; percent: number }) {
  const circumference = 2 * Math.PI * 36
  const strokeDashoffset = circumference - (percent / 100) * circumference

  const getColor = () => {
    if (percent >= 90) return '#ef4444' // red-500
    if (percent >= 70) return '#eab308' // yellow-500
    return '#10b981' // emerald-500
  }

  return (
    <div className="relative w-24 h-24">
      <svg className="w-full h-full -rotate-90" viewBox="0 0 80 80">
        {/* Background circle */}
        <circle
          cx="40"
          cy="40"
          r="36"
          stroke="currentColor"
          strokeWidth="6"
          fill="none"
          className="text-slate-700"
        />
        {/* Progress circle */}
        <motion.circle
          cx="40"
          cy="40"
          r="36"
          stroke={getColor()}
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-semibold text-white">{used.toFixed(0)}</span>
        <span className="text-xs text-slate-500">/ {total.toFixed(0)} MB</span>
      </div>
    </div>
  )
}

export function SystemStats() {
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStats = async () => {
    console.log('[SystemStats] Starting fetch...')
    try {
      // Use relative URL to avoid CORS issues
      const url = '/health'
      console.log('[SystemStats] Fetching:', url)
      const res = await fetch(url)
      console.log('[SystemStats] Response status:', res.status, res.statusText)
      const text = await res.text()
      console.log('[SystemStats] Response text:', text)
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${text}`)
      const data = JSON.parse(text)
      console.log('[SystemStats] Parsed data:', data)
      setStats(data.system)
      setError(null)
    } catch (err) {
      console.error('[SystemStats] Error:', err)
      setError('Unable to load system stats')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 5000) // Refresh every 5s
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="bg-slate-800/30 rounded-xl p-3 flex items-center gap-3">
        <div className="w-4 h-4 border border-slate-600 border-t-violet-500 rounded-full animate-spin" />
        <span className="text-xs text-slate-500">Loading...</span>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="bg-slate-800/30 rounded-xl p-3">
        <p className="text-xs text-slate-500">{error || 'No system data'}</p>
      </div>
    )
  }

  return (
    <div className="bg-slate-800/30 rounded-xl p-3 border border-slate-800/60">
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-slate-500">CPU</span>
          <span className={`font-mono ${(stats.cpu_percent ?? 0) >= 90 ? 'text-red-400' : 'text-slate-300'}`}>
            {stats.cpu_percent?.toFixed(0) ?? 'N/A'}%
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-500">RAM</span>
          <span className={`font-mono ${(stats.memory_percent ?? 0) >= 90 ? 'text-red-400' : 'text-slate-300'}`}>
            {stats.memory_percent?.toFixed(0) ?? 'N/A'}%
          </span>
        </div>
        {stats.gpu && (
          <div className="flex items-center gap-2">
            <span className="text-slate-500">GPU</span>
            <span className={`font-mono ${stats.gpu.utilization >= 90 ? 'text-red-400' : 'text-slate-300'}`}>
              {stats.gpu.utilization}%
            </span>
          </div>
        )}
        {stats.gpu?.temperature && (
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Temp</span>
            <span className={`font-mono ${stats.gpu.temperature >= 80 ? 'text-red-400' : 'text-slate-300'}`}>
              {stats.gpu.temperature}°C
            </span>
          </div>
        )}
      </div>
    </div>
  )
}