// components/agent/AgentCanvas.tsx
// POC — Agent Canvas: visual LangGraph pipeline with real-time node status
'use client'

import { memo, useCallback, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAgentStore } from '@/lib/stores/agentStore'
import { useChatStore } from '@/lib/stores/chatStore'

// ── Zoom/pan constants ────────────────────────────────────────────────

const MIN_ZOOM = 0.3
const MAX_ZOOM = 3.0
const ZOOM_STEP = 0.9  // multiplicative factor per wheel tick

// ── Pipeline definition ──────────────────────────────────────────────

interface PipelineNodeDef {
  id: string
  label: string
  description: string
  icon: string
}

const PIPELINE_NODES: PipelineNodeDef[] = [
  { id: 'step-analyzing',  label: 'Analyze',  description: 'Classify & route task',          icon: '🔍' },
  { id: 'step-planning',   label: 'Plan',     description: 'Structured implementation plan',  icon: '📋' },
  { id: 'step-coding',     label: 'Code',     description: 'Generate Python code',            icon: '⚙️' },
  { id: 'step-reviewing',  label: 'Review',   description: 'Static & LLM review',             icon: '👁️' },
  { id: 'step-executing',  label: 'Execute',  description: 'Sandboxed code execution',        icon: '▶️' },
]

const NODE_IDS = PIPELINE_NODES.map((n) => n.id)

// Edges: linear pipeline + fix loop
interface EdgeDef {
  from: string
  to: string
  label?: string
  dashed?: boolean
  condition?: string
}

const EDGES: EdgeDef[] = [
  { from: 'step-analyzing', to: 'step-planning' },
  { from: 'step-planning',  to: 'step-coding' },
  { from: 'step-coding',    to: 'step-reviewing' },
  { from: 'step-reviewing', to: 'step-executing' },
  { from: 'step-executing', to: 'step-coding', label: 'fix_code', dashed: true, condition: 'review failed' },
]

// ── Status config ────────────────────────────────────────────────────

type NodeStatus = 'pending' | 'active' | 'completed' | 'error'

const STATUS_STYLES: Record<NodeStatus, { stroke: string; fill: string; glow: string; text: string }> = {
  pending:   { stroke: '#334155', fill: '#1e293b', glow: 'rgba(51,65,85,0)',     text: '#64748b' },
  active:    { stroke: '#8b5cf6', fill: '#2e1065', glow: 'rgba(139,92,246,0.3)', text: '#c4b5fd' },
  completed: { stroke: '#34d399', fill: '#064e3b', glow: 'rgba(52,211,153,0.3)', text: '#6ee7b7' },
  error:     { stroke: '#f87171', fill: '#450a0a', glow: 'rgba(248,113,113,0.3)', text: '#fca5a5' },
}

// ── Layout constants (SVG viewBox: 0 0 580 720) ─────────────────────

const COL_WIDTH = 580
const ROW_HEIGHT = 100
const NODE_WIDTH = 180
const NODE_HEIGHT = 68
const START_Y = 40
const FIX_Y = 620  // fix_code node below the main pipeline

// Center-X for each column (main pipeline: column 0)
const CX = COL_WIDTH / 2

function nodeY(index: number) {
  return START_Y + index * ROW_HEIGHT
}

// ── Sub-components ───────────────────────────────────────────────────

interface NodeCardProps {
  nodeDef: PipelineNodeDef
  status: NodeStatus
  duration?: number
  tokens?: number
  isFixNode?: boolean
}

const NodeCard = memo(function NodeCard({ nodeDef, status, duration, tokens, isFixNode }: NodeCardProps) {
  const style = STATUS_STYLES[status]
  const isActive = status === 'active'
  const isPending = status === 'pending'

  return (
    <g>
      {/* Glow ring */}
      {isActive && (
        <motion.ellipse
          cx={CX}
          cy={isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))}
          rx={NODE_WIDTH / 2 + 12}
          ry={NODE_HEIGHT / 2 + 12}
          fill={style.glow}
          animate={{ opacity: [0.4, 0.8, 0.4] }}
          transition={{ repeat: Infinity, duration: 2 }}
        />
      )}

      {/* Node card */}
      <motion.rect
        x={CX - NODE_WIDTH / 2}
        y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) - NODE_HEIGHT / 2}
        width={NODE_WIDTH}
        height={NODE_HEIGHT}
        rx={12}
        fill={style.fill}
        stroke={style.stroke}
        strokeWidth={isActive ? 2 : 1.5}
        initial={false}
        animate={{
          strokeOpacity: isActive ? 1 : 0.6,
          scale: isActive ? 1.02 : 1,
        }}
        transition={{ duration: 0.3 }}
        className="cursor-pointer"
      />

      {/* Pulsing border for active */}
      {isActive && (
        <motion.rect
          x={CX - NODE_WIDTH / 2}
          y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) - NODE_HEIGHT / 2}
          width={NODE_WIDTH}
          height={NODE_HEIGHT}
          rx={12}
          fill="none"
          stroke={style.stroke}
          strokeWidth={2}
          animate={{ opacity: [0, 0.6, 0] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
        />
      )}

      {/* Icon */}
      <text
        x={CX - NODE_WIDTH / 2 + 14}
        y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) + 4}
        fontSize={18}
        textAnchor="middle"
        dominantBaseline="middle"
      >
        {isFixNode ? '🔄' : nodeDef.icon}
      </text>

      {/* Label */}
      <text
        x={CX - NODE_WIDTH / 2 + 36}
        y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) - 8}
        fill={style.text}
        fontSize={13}
        fontWeight={600}
        fontFamily="monospace"
      >
        {isFixNode ? 'Fix Code' : nodeDef.label}
      </text>

      {/* Description or status badge */}
      <text
        x={CX - NODE_WIDTH / 2 + 36}
        y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) + 12}
        fill={isPending ? '#475569' : '#94a3b8'}
        fontSize={10}
        fontFamily="monospace"
      >
        {isActive
          ? '▸ Running...'
          : status === 'completed'
            ? '✓ Done'
            : status === 'error'
              ? '✗ Failed'
              : nodeDef.description}
      </text>

      {/* Duration badge */}
      {duration !== undefined && duration > 0 && (
        <g>
          <rect
            x={CX + NODE_WIDTH / 2 - 52}
            y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) - NODE_HEIGHT / 2 + 6}
            width={46}
            height={16}
            rx={4}
            fill={status === 'completed' ? '#064e3b' : '#1e1b4b'}
            stroke={status === 'completed' ? '#34d399' : '#8b5cf6'}
            strokeWidth={0.5}
          />
          <text
            x={CX + NODE_WIDTH / 2 - 29}
            y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) - NODE_HEIGHT / 2 + 16}
            fill={status === 'completed' ? '#6ee7b7' : '#c4b5fd'}
            fontSize={9}
            textAnchor="middle"
            fontFamily="monospace"
          >
            {duration.toFixed(1)}s
          </text>
        </g>
      )}

      {/* Token count badge (below duration) */}
      {tokens !== undefined && tokens > 0 && (
        <g>
          <rect
            x={CX + NODE_WIDTH / 2 - 52}
            y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) - NODE_HEIGHT / 2 + 25}
            width={46}
            height={16}
            rx={4}
            fill={status === 'completed' ? '#0c4a6e' : '#1e1b4b'}
            stroke={status === 'completed' ? '#38bdf8' : '#8b5cf6'}
            strokeWidth={0.5}
          />
          <text
            x={CX + NODE_WIDTH / 2 - 29}
            y={(isFixNode ? FIX_Y : nodeY(NODE_IDS.indexOf(nodeDef.id))) - NODE_HEIGHT / 2 + 35}
            fill={status === 'completed' ? '#7dd3fc' : '#c4b5fd'}
            fontSize={9}
            textAnchor="middle"
            fontFamily="monospace"
          >
            {tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}k` : `${tokens}`} tok
          </text>
        </g>
      )}
    </g>
  )
})

NodeCard.displayName = 'NodeCard'

// ── Edge (arrow) component ───────────────────────────────────────────

interface EdgePathProps {
  edge: EdgeDef
  isActive: boolean
  isDone: boolean
}

const EdgePath = memo(function EdgePath({ edge, isActive, isDone }: EdgePathProps) {
  const fromIdx = NODE_IDS.indexOf(edge.from)
  const toIdx = edge.to === 'step-coding' && edge.condition
    ? NODE_IDS.indexOf('step-coding')  // fix loop back to coding
    : NODE_IDS.indexOf(edge.to)

  const isFixLoop = edge.condition !== undefined
  const strokeColor = isActive ? '#8b5cf6' : isDone ? '#34d399' : '#334155'

  // Calculate start/end points
  const y1 = isFixLoop
    ? nodeY(fromIdx) + NODE_HEIGHT / 2
    : nodeY(fromIdx) + NODE_HEIGHT / 2
  const y2 = isFixLoop
    ? FIX_Y - NODE_HEIGHT / 2    // down to fix node
    : nodeY(toIdx) - NODE_HEIGHT / 2

  // Fix loop: down from execute, then around back to code
  if (isFixLoop) {
    const midY = (nodeY(3) + ROW_HEIGHT + FIX_Y - NODE_HEIGHT / 2) / 2  // between review and execute? No.
    // Let's do a cleaner path: from bottom of execute, go down to fix node
    // Then fix node → code node (leftward)
    
    const startX = CX
    const endX = CX
    const codeNodeYPos = nodeY(2) // coding node Y
    
    return (
      <g>
        {/* Main arrow: execute down to fix */}
        <path
          d={`M ${startX} ${y1} L ${startX} ${FIX_Y - NODE_HEIGHT / 2}`}
          fill="none"
          stroke={strokeColor}
          strokeWidth={isActive ? 2.5 : 1.5}
          strokeDasharray={edge.dashed ? '5,4' : 'none'}
          opacity={isActive || isDone ? 0.8 : 0.3}
        />
        {/* Arrowhead */}
        <polygon
          points={`${endX - 5},${FIX_Y - NODE_HEIGHT / 2 - 8} ${endX + 5},${FIX_Y - NODE_HEIGHT / 2 - 8} ${endX},${FIX_Y - NODE_HEIGHT / 2 + 2}`}
          fill={strokeColor}
          opacity={isActive || isDone ? 0.8 : 0.3}
        />
        
        {/* Back arrow: fix → code (arch around) */}
        <path
          d={`M ${CX + NODE_WIDTH / 2 + 10} ${FIX_Y} 
              Q ${CX + NODE_WIDTH / 2 + 60} ${FIX_Y} 
                ${CX + NODE_WIDTH / 2 + 60} ${codeNodeYPos} 
              Q ${CX + NODE_WIDTH / 2 + 60} ${codeNodeYPos - 10} 
                ${CX + NODE_WIDTH / 2 + 10} ${codeNodeYPos}`}
          fill="none"
          stroke={edge.dashed ? '#f59e0b' : strokeColor}
          strokeWidth={1.5}
          strokeDasharray="5,4"
          opacity={0.7}
        />
        {/* Arrowhead on return path */}
        <polygon
          points={`${CX + NODE_WIDTH / 2 + 8},${codeNodeYPos - 5} ${CX + NODE_WIDTH / 2 + 12},${codeNodeYPos + 5} ${CX + NODE_WIDTH / 2 + 14},${codeNodeYPos - 5}`}
          fill="#f59e0b"
          opacity={0.7}
        />
        
        {/* Label on the return path */}
        <text
          x={CX + NODE_WIDTH / 2 + 65}
          y={codeNodeYPos + ROW_HEIGHT / 2 + 5}
          fill="#f59e0b"
          fontSize={9}
          fontFamily="monospace"
          opacity={0.8}
        >
          attempt N+1
        </text>
      </g>
    )
  }

  // Standard edge: straight down
  return (
    <g>
      <motion.path
        d={`M ${CX} ${y1} L ${CX} ${y2}`}
        fill="none"
        stroke={strokeColor}
        strokeWidth={isActive ? 2.5 : 1.5}
        strokeLinecap="round"
        strokeDasharray={edge.dashed ? '5,4' : 'none'}
        initial={false}
        animate={{
          strokeOpacity: isActive ? 1 : isDone ? 0.8 : 0.3,
        }}
        transition={{ duration: 0.3 }}
      />
      {/* Arrowhead */}
      <polygon
        points={`${CX - 5},${y2 - 8} ${CX + 5},${y2 - 8} ${CX},${y2 + 2}`}
        fill={strokeColor}
        opacity={isActive || isDone ? 0.8 : 0.3}
      />
      
      {/* Animated dot on active edge */}
      {isActive && (
        <motion.circle
          cx={CX}
          cy={y1}
          r={4}
          fill="#8b5cf6"
          animate={{ cy: [y1, y2] }}
          transition={{ repeat: Infinity, duration: 1.2, ease: 'easeInOut' }}
        />
      )}
    </g>
  )
})

EdgePath.displayName = 'EdgePath'

// ── Main component ───────────────────────────────────────────────────

interface AgentCanvasProps {
  className?: string
}

export function AgentCanvas({ className = '' }: AgentCanvasProps) {
  // Subscribe to agent steps from the central agentStore
  const agentSteps = useAgentStore((s) => s.steps)
  const isStreaming = useChatStore((s) => s.isLoading)

  // Derive status map from steps
  const nodeStatuses = useMemo(() => {
    const map = new Map<string, NodeStatus>()
    // Default all to pending
    for (const id of NODE_IDS) {
      map.set(id, 'pending')
    }

    let activeFound = false

    for (const step of agentSteps) {
      const id = step.id
      if (!NODE_IDS.includes(id)) continue

      const status: NodeStatus = step.status === 'done'
        ? 'completed'
        : step.status === 'error'
          ? 'error'
          : step.status as NodeStatus

      // Only first active node is shown as active; later ones stay pending
      if (status === 'active') {
        if (!activeFound) {
          activeFound = true
          map.set(id, 'active')
        } else {
          map.set(id, 'pending')
        }
      } else {
        map.set(id, status as NodeStatus)
      }
    }

    return map
  }, [agentSteps])

  // Duration map (from store steps or computed)
  const nodeDurations = useMemo(() => {
    const map = new Map<string, number>()
    for (const step of agentSteps) {
      if (step.duration) {
        map.set(step.id, step.duration)
      }
    }
    return map
  }, [agentSteps])

  // Token count map (from store steps)
  const nodeTokens = useMemo(() => {
    const map = new Map<string, number>()
    for (const step of agentSteps) {
      if (step.tokens) {
        map.set(step.id, step.tokens)
      }
    }
    return map
  }, [agentSteps])

  // Check if fix loop is active
  const hasFixingStep = useMemo(() =>
    agentSteps.some((s) => s.id === 'step-fixing' || s.id === 'step-fix_code'),
    [agentSteps]
  )

  const hasCompletedExecution = useMemo(() => {
    const execStep = agentSteps.find((s) => s.id === 'step-executing')
    return execStep?.status === 'done'
  }, [agentSteps])

  // ── Pan / Zoom state ───────────────────────────────────────────────
  const containerRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [panX, setPanX] = useState(0)
  const [panY, setPanY] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null)

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const container = containerRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    setScale((prev) => {
      const factor = e.deltaY > 0 ? ZOOM_STEP : 1 / ZOOM_STEP
      const newScale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, prev * factor))
      if (newScale === prev) return prev

      // Adjust pan so the point under cursor stays fixed
      setPanX((px) => mouseX - (mouseX - px) * (newScale / prev))
      setPanY((py) => mouseY - (mouseY - py) * (newScale / prev))
      return newScale
    })
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    // Only left button
    if (e.button !== 0) return
    setIsDragging(true)
    dragRef.current = { startX: e.clientX, startY: e.clientY, panX, panY }
  }, [panX, panY])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const drag = dragRef.current
    if (!drag) return
    setPanX(drag.panX + (e.clientX - drag.startX))
    setPanY(drag.panY + (e.clientY - drag.startY))
  }, [])

  const handleDragEnd = useCallback(() => {
    dragRef.current = null
    setIsDragging(false)
  }, [])

  const zoomIn = useCallback(() => {
    setScale((prev) => Math.min(MAX_ZOOM, prev / ZOOM_STEP))
  }, [])

  const zoomOut = useCallback(() => {
    setScale((prev) => Math.max(MIN_ZOOM, prev * ZOOM_STEP))
  }, [])

  const resetView = useCallback(() => {
    setScale(1)
    setPanX(0)
    setPanY(0)
  }, [])

  const zoomPercent = Math.round(scale * 100)

  // Cursor style
  const cursorStyle = isDragging ? 'grabbing' : 'grab'

  // SVG transform string
  const svgTransform = `translate(${panX}px, ${panY}px) scale(${scale})`

  return (
    <div className={`bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-violet-500/30 rounded-2xl p-4 shadow-lg shadow-violet-500/10 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">Agent Canvas</span>
          <span className="text-[10px] text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700">
            live
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {/* Zoom controls */}
          <div className="flex items-center gap-0.5 mr-2">
            <button
              onClick={zoomOut}
              className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              title="Zoom out"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
            <button
              onClick={resetView}
              className="px-1.5 py-0.5 rounded text-[10px] font-mono text-slate-400 hover:text-white hover:bg-slate-700 transition-colors min-w-[32px] text-center"
              title="Reset zoom"
            >
              {zoomPercent}%
            </button>
            <button
              onClick={zoomIn}
              className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              title="Zoom in"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="2" y1="6" x2="10" y2="6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                <line x1="6" y1="2" x2="6" y2="10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>

          {isStreaming && (
            <motion.span
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
              className="flex items-center gap-1 text-[10px] text-slate-500"
            >
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full" />
              streaming
            </motion.span>
          )}
        </div>
      </div>

      {/* SVG Canvas with pan/zoom */}
      <div
        ref={containerRef}
        className="relative overflow-hidden rounded-lg select-none"
        style={{ minHeight: '400px', maxHeight: '600px', cursor: cursorStyle }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleDragEnd}
        onMouseLeave={handleDragEnd}
      >
      <svg
        viewBox="0 0 580 720"
        className="w-full h-auto"
        style={{
          transform: svgTransform,
          transformOrigin: '0 0',
          minHeight: '400px',
          willChange: 'transform',
        }}
      >
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>

        {/* Background grid (subtle) */}
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1e293b" strokeWidth="0.5" />
        </pattern>
        <rect width={COL_WIDTH} height={720} fill="url(#grid)" opacity={0.3} />

        {/* Edges */}
        {EDGES.map((edge) => {
          const fromStatus = nodeStatuses.get(edge.from) ?? 'pending'
          const toStatus = nodeStatuses.get(edge.to === 'step-coding' && edge.condition ? 'step-coding' : edge.to) ?? 'pending'
          const isActive = fromStatus === 'active' || toStatus === 'active'
          const isDone = fromStatus === 'completed' || toStatus === 'completed'
          return (
            <EdgePath
              key={`${edge.from}→${edge.to}`}
              edge={edge}
              isActive={isActive}
              isDone={isDone}
            />
          )
        })}

        {/* Main pipeline nodes */}
        {PIPELINE_NODES.map((nodeDef) => (
          <NodeCard
            key={nodeDef.id}
            nodeDef={nodeDef}
            status={nodeStatuses.get(nodeDef.id) ?? 'pending'}
            duration={nodeDurations.get(nodeDef.id)}
            tokens={nodeTokens.get(nodeDef.id)}
          />
        ))}

        {/* Fix code node (shown when fixing) */}
        <AnimatePresence>
          {hasFixingStep && (
            <g>
              <motion.g
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
              >
                  <NodeCard
                    nodeDef={{
                      id: 'step-fix_code',
                      label: 'Fix Code',
                      description: 'Auto-correct & re-run',
                      icon: '🔄',
                    }}
                    status={
                      agentSteps.some((s) => (s.id === 'step-fixing' || s.id === 'step-fix_code') && (s.status === 'active'))
                        ? 'active'
                        : 'completed'
                    }
                    duration={nodeDurations.get('step-fixing') ?? nodeDurations.get('step-fix_code')}
                    tokens={nodeTokens.get('step-fixing') ?? nodeTokens.get('step-fix_code')}
                    isFixNode
                  />
              </motion.g>
            </g>
          )}
        </AnimatePresence>

        {/* Legend */}
        <g transform="translate(16, 690)">
          <rect x={0} y={0} width={200} height={20} rx={4} fill="#0f172a" opacity={0.8} />
          <circle cx={12} cy={10} r={3} fill="#64748b" />
          <text x={20} y={14} fill="#64748b" fontSize={8} fontFamily="monospace">pending</text>
          <circle cx={58} cy={10} r={3} fill="#8b5cf6" />
          <text x={66} y={14} fill="#8b5cf6" fontSize={8} fontFamily="monospace">active</text>
          <circle cx={103} cy={10} r={3} fill="#34d399" />
          <text x={111} y={14} fill="#34d399" fontSize={8} fontFamily="monospace">done</text>
          <circle cx={147} cy={10} r={3} fill="#f87171" />
          <text x={155} y={14} fill="#f87171" fontSize={8} fontFamily="monospace">error</text>
        </g>
      </svg>
      </div>

      {/* Compact pipeline summary */}
      <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-slate-700/50">
        {PIPELINE_NODES.map((nodeDef) => {
          const status = nodeStatuses.get(nodeDef.id) ?? 'pending'
          return (
            <div
              key={nodeDef.id}
              className="flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded"
              style={{
                backgroundColor: STATUS_STYLES[status].fill,
                color: STATUS_STYLES[status].text,
                borderColor: STATUS_STYLES[status].stroke,
                borderWidth: 1,
              }}
            >
              <span>{status === 'completed' ? '✓' : status === 'active' ? '●' : status === 'error' ? '✗' : '○'}</span>
              <span>{nodeDef.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
