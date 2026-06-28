// components/agent/AgentCanvas.tsx
// Agent Canvas orchestrator - React Flow graph visualization with timeline and controls
'use client'

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useAgentStore } from '@/lib/stores/agentStore'
import { useAgentCanvasStore } from '@/lib/stores'
import { sendApprovalDecision } from '@/services/canvasWebSocket'
import GraphVisualization from '../canvas/GraphVisualization'
import { CanvasControls } from './CanvasControls'
import { ExecutionTimeline } from './ExecutionTimeline'
import { NodeDetailPanel } from './NodeDetailPanel'
import { NodePalette } from './NodePalette'
import { useI18n } from '@/lib/i18n'
import { events } from '@/lib/events'
import CanvasParticles from './CanvasParticles'
import SuccessConfetti from './SuccessConfetti'

// ── Pipeline metadata (for detail panel) ──────────────────────────────

const PIPELINE_DEFS = [
  { id: 'step-orchestrator', label: 'Orchestrator', description: 'Pipeline coordinator' },
  { id: 'step-analyzing', label: 'Analyze',     description: 'Classify & route task' },
  { id: 'step-planning',  label: 'Plan',        description: 'Structured implementation plan' },
  { id: 'step-coding',    label: 'Code',        description: 'Generate Python code' },
  { id: 'step-reviewing', label: 'Review',      description: 'Static & LLM review' },
  { id: 'step-executing', label: 'Execute',     description: 'Sandboxed code execution' },
  { id: 'step-fixing',    label: 'Fix',        description: 'Auto-fix correction loop' },
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

  // Canvas store — UI state, selection, approval, session
  const selectedNodeId = useAgentCanvasStore((s) => s.selectedNodeId)
  const approvalStatus = useAgentCanvasStore((s) => s.approvalStatus)
  const isRunning = useAgentCanvasStore((s) => s.isRunning)
  const canvasSteps = useAgentCanvasStore((s) => s.steps)
  const setApprovalStatus = useAgentCanvasStore((s) => s.setApprovalStatus)
  const setSelectedNode = useAgentCanvasStore((s) => s.setSelectedNode)


  // Subscribe to awaitingApproval event from chatService/MessageHandler
  // This is the bridge: backend emits AWAITING_APPROVAL → MessageHandler calls
  // chatService.handleApproval → events.emit('awaitingApproval') → we update the store
  useEffect(() => {
    const unsubscribe = events.on('awaitingApproval', () => {
      setApprovalStatus('PENDING')
    })
    return unsubscribe
  }, [setApprovalStatus])

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
    setSelectedNode(nodeId)
  }, [setSelectedNode])

  const handleCloseDetail = useCallback(() => {
    setSelectedNode(null)
  }, [setSelectedNode])

  const hasSteps = agentSteps.length > 0
  const isActive = agentSteps.some((s) => s.status === 'active')
  const showSuccess = agentSteps.some((s) => s.status === 'done')

  return (
    <div className={`flex flex-col h-full agent-canvas ${className} relative`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">
            {t.canvas?.title || 'Agent Canvas'}
          </span>
          {isRunning && ( // was canvasIsRunning
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
          <CanvasParticles isActive={isActive} />
          <SuccessConfetti trigger={showSuccess} intensity="medium" />
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
              done: 'bg-emerald-500 shadow-emerald-500/50',
              active: 'bg-violet-500 shadow-violet-500/50',
              error: 'bg-red-500 shadow-red-500/50',
              pending: 'bg-slate-600',
            }
            const isActive = status === 'active'
            const isCompleted = status === 'done'
            return (
              <div
                key={nodeDef.id}
                className={`flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1.5 rounded-lg transition-all duration-300 ${
                  isActive
                    ? 'bg-violet-500/15 border border-violet-500/30 shadow-sm shadow-violet-500/20'
                    : isCompleted
                    ? 'bg-emerald-500/10 border border-emerald-500/20'
                    : 'bg-slate-800/40 border border-slate-700/30 hover:bg-slate-700/50'
                }`}
                title={nodeDef.description}
              >
                <span className={`w-2 h-2 rounded-full ${statusColors[status] || 'bg-slate-600'} ${isActive ? 'animate-pulse' : ''}`} />
                <span className="text-slate-400">{nodeDef.label}</span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
