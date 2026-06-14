// components/agent/AgentCanvas.tsx
// Agent Canvas orchestrator - React Flow graph visualization with timeline and controls
'use client'

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAgentStore } from '@/lib/stores/agentStore'
import { useAgentCanvasStore } from '@/lib/stores'
import { useCanvasWebSocket, sendApprovalDecision } from '@/services/canvasWebSocket'
import GraphVisualization from '../canvas/GraphVisualization'
import { CanvasControls } from './CanvasControls'
import { ExecutionTimeline } from './ExecutionTimeline'
import { NodeDetailPanel } from './NodeDetailPanel'
import { NodePalette } from './NodePalette'
import { useI18n } from '@/lib/i18n'

// ── Pipeline metadata (for detail panel) ──────────────────────────────

const PIPELINE_DEFS = [
  { id: 'step-analyzing', label: 'Analyze',     description: 'Classify & route task' },
  { id: 'step-planning',  label: 'Plan',        description: 'Structured implementation plan' },
  { id: 'step-coding',    label: 'Code',        description: 'Generate Python code' },
  { id: 'step-reviewing', label: 'Review',      description: 'Static & LLM review' },
  { id: 'step-executing', label: 'Execute',     description: 'Sandboxed code execution' },
]

// ── Props ─────────────────────────────────────────────────────────────

interface AgentCanvasProps {
  className?: string
  /** Show in split-view mode (compact layout, no timeline sidebar) */
  splitView?: boolean
  /** Callback when user requests split view toggle */
  onSplitViewToggle?: () => void
}

// ── Component ─────────────────────────────────────────────────────────

export function AgentCanvas({
  className = '',
  splitView = false,
  onSplitViewToggle,
}: AgentCanvasProps) {
  const { t } = useI18n()
  const agentSteps = useAgentStore((s) => s.steps)

  // Canvas store — UI state, approval status, session
  const selectedNodeId = useAgentCanvasStore((s) => s.selectedNodeId)
  const approvalStatus = useAgentCanvasStore((s) => s.approvalStatus)
  const canvasSessionId = useAgentCanvasStore((s) => s.sessionId)
  const canvasIsRunning = useAgentCanvasStore((s) => s.isRunning)
  const canvasSteps = useAgentCanvasStore((s) => s.steps)

  // WebSocket — connect to receive real-time step/approval/run events
  useCanvasWebSocket(canvasSessionId ?? undefined)

  // Sync agentStore steps into canvas store so both stay in sync
  const { setSteps } = useAgentCanvasStore()
  useEffect(() => {
    setSteps(
      agentSteps.map((s) => ({
        name: s.id,
        status: s.status === 'active' ? 'running' : (s.status as 'pending' | 'running' | 'done' | 'error'),
        durationMs: s.duration ? s.duration * 1000 : undefined,
        tokens: s.tokens,
        startedAt: undefined,
        error: s.detail,
      })),
    )
  }, [agentSteps, setSteps])

  // Palette open/close
  const [paletteOpen, setPaletteOpen] = useState(false)

  // React Flow instance ref (for export)
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  // Find selected step
  const selectedStep = useMemo(() => {
    if (!selectedNodeId) return null
    return agentSteps.find((s) => s.id === selectedNodeId) || null
  }, [selectedNodeId, agentSteps])

  const selectedNodeDef = useMemo(() => {
    if (!selectedNodeId) return null
    return PIPELINE_DEFS.find((n) => n.id === selectedNodeId) || null
  }, [selectedNodeId])

  // ── Export ──────────────────────────────────────────────────────────

  const handleExportPng = useCallback(() => {
    // Capture the React Flow SVG element and convert to PNG via a temp canvas
    const svgEl = reactFlowWrapper.current?.querySelector('.react-flow__renderer svg')
    if (!svgEl) return

    const svgData = new XMLSerializer().serializeToString(svgEl)
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)

    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.width * 2
      canvas.height = img.height * 2
      const ctx = canvas.getContext('2d')
      if (!ctx) { URL.revokeObjectURL(url); return }
      ctx.scale(2, 2)
      ctx.fillStyle = '#0b0f14'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(url)

      const link = document.createElement('a')
      link.download = `agent-canvas-${Date.now()}.png`
      link.href = canvas.toDataURL('image/png')
      link.click()
    }
    img.src = url
  }, [])

  const handleExportJson = useCallback(() => {
    const data = JSON.stringify(
      {
        exportedAt: new Date().toISOString(),
        steps: agentSteps,
        pipeline: PIPELINE_DEFS,
      },
      null,
      2,
    )
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.download = `agent-canvas-${Date.now()}.json`
    link.href = url
    link.click()
    URL.revokeObjectURL(url)
  }, [agentSteps])

  const handleNodeClick = useCallback((nodeId: string) => {
    useAgentCanvasStore.getState().setSelectedNode(nodeId)
  }, [])

  const handleCloseDetail = useCallback(() => {
    useAgentCanvasStore.getState().setSelectedNode(null)
  }, [])

  const hasSteps = agentSteps.length > 0

  return (
    <div className={`flex flex-col h-full bg-[#0b0f14] ${className} relative`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">
            {t.canvas?.title || 'Agent Canvas'}
          </span>
          {canvasIsRunning && (
            <motion.span
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
              className="flex items-center gap-1 text-[10px] text-slate-500"
            >
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full" />
              {t.canvas?.live || 'live'}
            </motion.span>
          )}
        </div>

        {/* Approval banner */}
        {approvalStatus === 'PENDING' && (
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-amber-400 font-medium">
              ⏳ {t.canvas?.approvalPending || 'Awaiting approval'}
            </span>
            <button
              onClick={() => sendApprovalDecision('APPROVED')}
              className="text-[10px] font-mono px-2 py-1 rounded-md bg-emerald-600/20 text-emerald-400 border border-emerald-600/30 hover:bg-emerald-600/30 transition-colors"
            >
              {t.canvas?.approve || 'Approve'}
            </button>
            <button
              onClick={() => sendApprovalDecision('REJECTED', 'User cancelled')}
              className="text-[10px] font-mono px-2 py-1 rounded-md bg-red-600/20 text-red-400 border border-red-600/30 hover:bg-red-600/30 transition-colors"
            >
              {t.canvas?.reject || 'Reject'}
            </button>
          </div>
        )}
      </div>

      {/* Controls */}
      <CanvasControls
        onExportPng={handleExportPng}
        onExportJson={handleExportJson}
        onSplitView={onSplitViewToggle}
        splitViewActive={splitView}
        showSplitView={!!onSplitViewToggle}
        paletteOpen={paletteOpen}
        onTogglePalette={() => setPaletteOpen((p) => !p)}
      />

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Node palette */}
        <NodePalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} />
        {/* Graph area */}
        <div ref={reactFlowWrapper} className="flex-1 relative">
          {hasSteps ? (
            <GraphVisualization steps={canvasSteps} onNodeClick={handleNodeClick} />
          ) : (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
              {t.canvas?.noData || 'No execution data yet'}
            </div>
          )}

          {/* Node detail panel (overlay) */}
          <NodeDetailPanel
            nodeId={selectedNodeId}
            step={selectedStep}
            nodeDef={selectedNodeDef}
            onClose={handleCloseDetail}
          />
        </div>

        {/* Timeline sidebar (only in standalone mode) */}
        {!splitView && hasSteps && (
          <ExecutionTimeline
            steps={agentSteps}
            selectedNodeId={selectedNodeId}
            onNodeSelect={handleNodeClick}
          />
        )}
      </div>

      {/* Pipeline status bar (bottom) */}
      {hasSteps && (
        <div className="flex items-center gap-1.5 px-4 py-2 border-t border-slate-700/50 bg-slate-900/50">
          {PIPELINE_DEFS.map((nodeDef) => {
            const step = agentSteps.find((s) => s.id === nodeDef.id)
            const status = step?.status || 'pending'
            const statusColors: Record<string, string> = {
              done: 'bg-emerald-500',
              active: 'bg-violet-500',
              error: 'bg-red-500',
              pending: 'bg-slate-600',
            }
            return (
              <div
                key={nodeDef.id}
                className="flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded-md bg-slate-800/50"
              >
                <span className={`w-2 h-2 rounded-full ${statusColors[status] || 'bg-slate-600'}`} />
                <span className="text-slate-400">{nodeDef.label}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
