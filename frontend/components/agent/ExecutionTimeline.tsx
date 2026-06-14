// components/agent/ExecutionTimeline.tsx
// Vertical timeline sidebar with filtering, select-all, and status badges

'use client'

import { memo, useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import type { AgentStep, AgentStepStatus } from '@/lib/types'

interface ExecutionTimelineProps {
  steps: AgentStep[]
  selectedNodeId?: string | null
  onNodeSelect?: (nodeId: string) => void
}

type StatusFilter = 'all' | AgentStepStatus

const FILTERS: { key: StatusFilter; label: string; color: string }[] = [
  { key: 'all',    label: 'All',    color: 'text-slate-400 border-slate-500' },
  { key: 'active', label: 'Active', color: 'text-violet-400 border-violet-500' },
  { key: 'done',   label: 'Done',   color: 'text-emerald-400 border-emerald-500' },
  { key: 'error',  label: 'Error',  color: 'text-red-400 border-red-500' },
  { key: 'pending',label: 'Pending',color: 'text-slate-500 border-slate-600' },
]

const DOT_STYLES: Record<string, { bg: string; glow: string }> = {
  active:    { bg: 'bg-violet-500',   glow: 'shadow-violet-500/50' },
  done:      { bg: 'bg-emerald-500',  glow: 'shadow-emerald-500/50' },
  error:     { bg: 'bg-red-500',      glow: 'shadow-red-500/50' },
  pending:   { bg: 'bg-slate-600',    glow: '' },
}

const TimelineEntry = memo(function TimelineEntry({
  step,
  isSelected,
  isLast,
  onSelect,
}: {
  step: AgentStep
  isSelected: boolean
  isLast: boolean
  onSelect: () => void
}) {
  const dot = DOT_STYLES[step.status] || DOT_STYLES.pending
  const isActive = step.status === 'active'

  return (
    <div
      onClick={onSelect}
      className={`relative pl-8 pr-3 py-3 cursor-pointer transition-colors group ${
        isSelected ? 'bg-slate-700/30' : 'hover:bg-slate-700/20'
      }`}
    >
      {/* Vertical line */}
      {!isLast && (
        <div className="absolute left-[10px] top-[14px] bottom-0 w-px bg-slate-700/50 group-hover:bg-slate-600/50 transition-colors" />
      )}

      {/* Status dot */}
      <div className="absolute left-[7px] top-[14px]">
        {isActive ? (
          <motion.div
            className={`w-2.5 h-2.5 rounded-full ${dot.bg} shadow-lg ${dot.glow}`}
            animate={{ scale: [1, 1.4, 1], opacity: [1, 0.7, 1] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
          />
        ) : (
          <div className={`w-2.5 h-2.5 rounded-full ${dot.bg} ${dot.glow ? `shadow-sm ${dot.glow}` : ''}`} />
        )}
      </div>

      {/* Content */}
      <div className="min-w-0">
        <div className="text-sm font-medium truncate text-slate-200 group-hover:text-white transition-colors">
          {step.title}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {step.duration !== undefined && step.duration > 0 && (
            <span className="text-[10px] font-mono text-slate-500 shrink-0">
              {step.duration.toFixed(1)}s
            </span>
          )}
          {step.tokens !== undefined && step.tokens > 0 && (
            <span className="text-[10px] font-mono text-slate-600 shrink-0">
              {step.tokens >= 1000 ? `${(step.tokens / 1000).toFixed(1)}k` : step.tokens} tok
            </span>
          )}
        </div>
        {step.detail && (
          <p className="text-[11px] text-slate-500 leading-snug mt-0.5 line-clamp-2">
            {step.detail}
          </p>
        )}
      </div>
    </div>
  )
})

TimelineEntry.displayName = 'TimelineEntry'

export function ExecutionTimeline({ steps, selectedNodeId, onNodeSelect }: ExecutionTimelineProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  const filteredSteps = useMemo(() => {
    if (statusFilter === 'all') return steps
    return steps.filter((s) => s.status === statusFilter)
  }, [steps, statusFilter])

  const stepCounts = useMemo(() => {
    const counts: Record<string, number> = { all: steps.length }
    for (const s of steps) {
      counts[s.status] = (counts[s.status] || 0) + 1
    }
    return counts
  }, [steps])

  const handleSelectAll = () => {
    // Select the first filtered step (or toggle behavior)
    if (filteredSteps.length > 0) {
      onNodeSelect?.(filteredSteps[0].id)
    }
  }

  const handleDeselectAll = () => {
    onNodeSelect?.('')
  }

  if (steps.length === 0) return null

  return (
    <div className="w-56 shrink-0 flex flex-col border-l border-slate-700/50 bg-slate-900/50">
      {/* Header with filter */}
      <div className="px-3 py-2 border-b border-slate-700/50 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
            Timeline
          </span>
          <span className="text-[10px] font-mono text-slate-600">
            {filteredSteps.length}/{steps.length}
          </span>
        </div>

        {/* Filter pills */}
        <div className="flex gap-1">
          {FILTERS.map((f) => {
            const count = stepCounts[f.key] || 0
            const isActive = statusFilter === f.key
            return (
              <button
                key={f.key}
                onClick={() => setStatusFilter(f.key)}
                disabled={count === 0 && !isActive}
                className={`text-[10px] font-mono px-1.5 py-0.5 rounded-md border transition-all ${
                  isActive
                    ? `${f.color} bg-slate-700/50`
                    : 'border-transparent text-slate-600 hover:text-slate-400 hover:border-slate-700'
                } disabled:opacity-30 disabled:cursor-not-allowed`}
              >
                {f.label}
                <span className="ml-0.5 opacity-60">{count}</span>
              </button>
            )
          })}
        </div>

        {/* Select All / Deselect All */}
        <div className="flex gap-2 pt-0.5">
          <button
            onClick={handleSelectAll}
            className="text-[10px] font-mono text-slate-500 hover:text-slate-300 transition-colors"
          >
            Select All
          </button>
          <button
            onClick={handleDeselectAll}
            className="text-[10px] font-mono text-slate-600 hover:text-slate-400 transition-colors"
          >
            Deselect All
          </button>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto py-1">
        {filteredSteps.length === 0 ? (
          <div className="px-4 py-6 text-center text-[11px] text-slate-600">
            No {statusFilter} steps
          </div>
        ) : (
          filteredSteps.map((step, i) => (
            <TimelineEntry
              key={step.id}
              step={step}
              isSelected={selectedNodeId === step.id}
              isLast={i === filteredSteps.length - 1 && steps.indexOf(step) === steps.length - 1}
              onSelect={() => onNodeSelect?.(step.id)}
            />
          ))
        )}
      </div>
    </div>
  )
}
