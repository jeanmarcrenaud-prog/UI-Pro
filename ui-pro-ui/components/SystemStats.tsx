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
      // Use explicit localhost to avoid any proxy issues
      const url = 'http://127.0.0.1:8000/health'
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
      <div className="animate-pulse space-y-4">
        <div className="h-20 bg-slate-800/50 rounded-xl" />
        <div className="h-20 bg-slate-800/50 rounded-xl" />
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="bg-slate-800/30 rounded-xl p-4 border border-slate-800/60">
        <p className="text-sm text-slate-500">{error || 'No system data available'}</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* CPU & Memory Row */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-800/60">
          <VUMeter
            value={stats.cpu_percent ?? 0}
            label="CPU"
            color="cpu"
            sublabel={stats.cpu_percent !== null ? `${stats.cpu_percent >= 90 ? 'High' : 'Normal'} usage` : undefined}
          />
        </div>
        
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-800/60">
          <VUMeter
            value={stats.memory_percent ?? 0}
            label="Memory"
            color="memory"
            sublabel={stats.memory_percent !== null ? `${stats.memory_percent >= 90 ? 'High' : 'Normal'} usage` : undefined}
          />
        </div>
      </div>

      {/* GPU Section */}
      {stats.gpu && (
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-800/60">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-sm font-medium text-slate-300 flex items-center gap-2">
              <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
              GPU
            </h4>
            <span className="text-xs text-emerald-400 font-mono">{stats.gpu.name}</span>
          </div>

          {/* GPU VUMeter */}
          <div className="mb-4">
            <VUMeter
              value={stats.gpu.utilization}
              label="GPU Utilization"
              color="gpu"
              sublabel={`${stats.gpu.utilization >= 90 ? 'High' : 'Normal'} load`}
            />
          </div>

          {/* GPU Memory & Temp Row */}
          <div className="flex items-center gap-6">
            <MemoryGauge
              used={stats.gpu.memory_used_mb}
              total={stats.gpu.memory_total_mb}
              percent={stats.gpu.memory_percent}
            />
            
            {stats.gpu.temperature !== null && (
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                <div>
                  <p className="text-lg font-semibold text-white">{stats.gpu.temperature}°C</p>
                  <p className="text-xs text-slate-500">Temperature</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* No GPU detected */}
      {!stats.gpu && (
        <div className="bg-slate-800/30 rounded-xl p-4 border border-dashed border-slate-700">
          <div className="flex items-center gap-3 text-slate-500">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <p className="text-sm">No GPU detected or nvidia-smi unavailable</p>
          </div>
        </div>
      )}
    </div>
  )
}