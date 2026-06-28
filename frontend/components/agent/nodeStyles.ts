// nodeStyles.ts
// Shared utilities for Canvas custom nodes — class generation, icon mapping, status helpers

import type { LucideIcon } from 'lucide-react'
import {
  Brain,
  Code2,
  PlayCircle,
  CheckCircle,
  AlertCircle,
  Clock,
  XCircle,
  Play,
} from 'lucide-react'

/** Map a step name (e.g. 'step-analyzing') to its Lucide icon */
export const iconMap: Record<string, LucideIcon> = {
  analyzing: Brain,
  planning: PlayCircle,
  coding: Code2,
  reviewing: CheckCircle,
  executing: Play,
  fixing: AlertCircle,
  fix: AlertCircle,
  progress: Clock,
  orchestrator: Brain,
  success: CheckCircle,
  execution_success: CheckCircle,
  max_attempts_reached: XCircle,
  execution_failed: XCircle,
  no_code_short_circuit: AlertCircle,
  cancelled: XCircle,
  error: XCircle,
}

/** Resolve the icon for a step given its name/id */
export function getIcon(name: string): LucideIcon {
  // Try the full name first, then extract prefix after 'step-'
  if (iconMap[name]) return iconMap[name]
  const prefix = name.replace(/^step-/, '')
  return iconMap[prefix] || Brain
}

/** Return the Tailwind colour class for a given step status */
export function getStatusColor(status: string): string {
  switch (status) {
    case 'running':
      return 'text-sky-400'
    case 'done':
      return 'text-emerald-400'
    case 'error':
      return 'text-red-400'
    case 'awaiting_approval':
      return 'text-amber-400'
    default:
      return 'text-slate-400'
  }
}

/** Build the full CSS class string for a node, matching globals.css definitions */
export function getNodeClasses(id: string, name: string, status: string): string {
  const typeMap: Record<string, string> = {
    'step-orchestrator': 'node-orchestrator',
    'step-analyzing': 'node-analyzing',
    'step-planning': 'node-planning',
    'step-coding': 'node-coding',
    'step-reviewing': 'node-reviewing',
    'step-executing': 'node-executing',
    'step-execution_success': 'node-success',
    'step-execution_failed': 'node-failed',
    'step-max_attempts_reached': 'node-failed',
    'step-no_code_short_circuit': 'node-skip',
    'step-fixing': 'node-fix',
    'step-cancelled': 'node-cancelled',
  }

  let cls = 'canvas-node'
  cls += ' ' + (typeMap[name] || '')

  if (status === 'done') cls += ' node-completed node-success'
  else if (status === 'error') cls += ' node-error'
  else if (status === 'pending') cls += ' node-waiting'
  else if (status === 'awaiting_approval') cls += ' node-waiting'

  if (status === 'running') cls += ' node-active'

  if (id?.includes('progress') || id?.includes('orchestrator')) {
    cls += ' node-step-progress'
  }

  // node-fix is already set via typeMap for step-fixing
  // Add it explicitly for name-based fix detection (overrides)
  if (name === 'step-fixing' && !cls.includes('node-fix')) {
    cls += ' node-fix'
  }

  return cls.trim()
}
