// components/agent/GraphVisualization.tsx
// React Flow visualization of the LangGraph agent pipeline

import React, { memo, useMemo, useEffect, useCallback, useState } from 'react'
import ReactFlow, {
  Handle, Position, NodeProps,
  Controls, MiniMap, Background, BackgroundVariant,
  useNodesState, useEdgesState, useReactFlow,
  Node as RFNode, Edge, MarkerType,
  ReactFlowProvider,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { AgentStep } from '@/lib/types'
import type { PaletteNodeDef } from './NodePalette'

// ── Constants ────────────────────────────────────────────────────────

const PIPELINE_DEFS = [
  { id: 'step-analyzing', label: 'Analyze',     icon: '🔍', description: 'Classify & route task' },
  { id: 'step-planning',  label: 'Plan',        icon: '📋', description: 'Implementation plan' },
  { id: 'step-coding',    label: 'Code',        icon: '⚙️', description: 'Generate Python code' },
  { id: 'step-reviewing', label: 'Review',      icon: '👁️', description: 'Static & LLM review' },
  { id: 'step-executing', label: 'Execute',     icon: '▶️', description: 'Sandboxed execution' },
] as const

const NODE_WIDTH = 200
const NODE_HEIGHT = 80
const H_GAP = 260
const V_GAP = 120

type StepStatus = 'pending' | 'active' | 'done' | 'error'

const STATUS_THEME: Record<StepStatus, { border: string; fill: string; text: string; dot: string }> = {
  pending:   { border: '#334155', fill: '#1e293b', text: '#64748b', dot: '#475569' },
  active:    { border: '#8b5cf6', fill: '#2e1065', text: '#c4b5fd', dot: '#8b5cf6' },
  done:      { border: '#34d399', fill: '#064e3b', text: '#6ee7b7', dot: '#34d399' },
  error:     { border: '#f87171', fill: '#450a0a', text: '#fca5a5', dot: '#f87171' },
}

// ── Custom Node ───────────────────────────────────────────────────────

const AgentNode = memo(function AgentNode({ data }: NodeProps) {
  const { label, icon, status, duration, tokens } = data
  const theme = STATUS_THEME[status as StepStatus] || STATUS_THEME.pending
  const isActive = status === 'active'

  return (
    <div
      className="rounded-xl border-2 shadow-xl px-4 py-3 min-w-[180px] transition-all duration-300"
      style={{
        backgroundColor: theme.fill,
        borderColor: theme.border,
        boxShadow: isActive ? `0 0 20px ${theme.border}44` : undefined,
      }}
    >
      {/* Handles */}
      <Handle type="target" position={Position.Left} style={{ background: theme.border, width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} style={{ background: theme.border, width: 8, height: 8 }} />

      {/* Icon + label row */}
      <div className="flex items-center gap-2.5">
        <span className="text-lg">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold truncate" style={{ color: theme.text }}>
            {label}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span
              className={`w-2 h-2 rounded-full ${isActive ? 'animate-pulse' : ''}`}
              style={{ backgroundColor: theme.dot }}
            />
            <span className="text-[10px] font-mono" style={{ color: theme.text, opacity: 0.7 }}>
              {isActive ? 'Running...' : status === 'done' ? '✓ Done' : status === 'error' ? '✗ Failed' : 'Pending'}
            </span>
          </div>
        </div>
      </div>

      {/* Duration + tokens row */}
      {(duration !== undefined || tokens !== undefined) && (
        <div className="flex items-center gap-2 mt-2 pt-2 border-t" style={{ borderColor: theme.border + '44' }}>
          {duration !== undefined && duration > 0 && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ backgroundColor: theme.border + '22', color: theme.text }}>
              {duration.toFixed(1)}s
            </span>
          )}
          {tokens !== undefined && tokens > 0 && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded" style={{ backgroundColor: theme.border + '22', color: theme.text }}>
              {tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}k` : tokens} tok
            </span>
          )}
        </div>
      )}
    </div>
  )
})

AgentNode.displayName = 'AgentNode'

const nodeTypes = { agentNode: AgentNode }

// ── Main Component ────────────────────────────────────────────────────

interface GraphVisualizationProps {
  steps: AgentStep[]
  onNodeClick?: (nodeId: string) => void
  paletteOpen?: boolean
  onNodesUpdate?: (nodes: RFNode[]) => void
}

export function GraphVisualization(props: GraphVisualizationProps) {
  return (
    <ReactFlowProvider>
      <GraphVisualizationInner {...props} />
    </ReactFlowProvider>
  )
}

function GraphVisualizationInner({ steps, onNodeClick, paletteOpen, onNodesUpdate }: GraphVisualizationProps) {
  const reactFlowInstance = useReactFlow()

  // Build status map from steps
  const statusMap = useMemo(() => {
    const map = new Map<string, StepStatus>()
    for (const step of steps) {
      map.set(step.id, step.status === 'done' ? 'done' : step.status as StepStatus)
    }
    return map
  }, [steps])

  const durationMap = useMemo(() => {
    const map = new Map<string, number>()
    for (const step of steps) {
      if (step.duration) map.set(step.id, step.duration)
    }
    return map
  }, [steps])

  const tokenMap = useMemo(() => {
    const map = new Map<string, number>()
    for (const step of steps) {
      if (step.tokens) map.set(step.id, step.tokens)
    }
    return map
  }, [steps])

  // Generate nodes
  const initialNodes: RFNode[] = useMemo(() => {
    return PIPELINE_DEFS.map((def, i) => ({
      id: def.id,
      type: 'agentNode',
      position: { x: i * H_GAP + 40, y: V_GAP },
      data: {
        label: def.label,
        icon: def.icon,
        status: statusMap.get(def.id) ?? 'pending',
        duration: durationMap.get(def.id),
        tokens: tokenMap.get(def.id),
      },
    }))
  }, [statusMap, durationMap, tokenMap])

  // Generate edges (linear pipeline + fix loop)
  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = []
    // Linear edges
    for (let i = 0; i < PIPELINE_DEFS.length - 1; i++) {
      const sourceStatus = statusMap.get(PIPELINE_DEFS[i].id)
      const targetStatus = statusMap.get(PIPELINE_DEFS[i + 1].id)
      const isActive = targetStatus === 'active'
      const isDone = sourceStatus === 'done'

      edges.push({
        id: `e${i}`,
        source: PIPELINE_DEFS[i].id,
        target: PIPELINE_DEFS[i + 1].id,
        animated: isActive,
        style: {
          stroke: isDone ? '#34d399' : isActive ? '#8b5cf6' : '#334155',
          strokeWidth: isActive ? 2.5 : 1.5,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isDone ? '#34d399' : isActive ? '#8b5cf6' : '#334155',
        },
      })
    }

    // Fix loop edge (executing → coding)
    const hasFix = steps.some(s => s.id === 'step-fixing' || s.id === 'step-fix_code')

    if (hasFix) {
      edges.push({
        id: 'e-fix',
        source: 'step-executing',
        target: 'step-coding',
        animated: true,
        style: {
          stroke: '#f59e0b',
          strokeWidth: 1.5,
          strokeDasharray: '5,5',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#f59e0b',
        },
        label: 'fix',
      })
    }

    return edges
  }, [statusMap, steps])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  // Sync when steps change
  useEffect(() => {
    setNodes(initialNodes)
    setEdges(initialEdges)
  }, [initialNodes, initialEdges, setNodes, setEdges])

  // Track extra nodes dropped from palette
  const [extraNodes, setExtraNodes] = useState<RFNode[]>([])

  // Drag-over handler: allow drop
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  // Drop handler: create new node from palette
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const raw = event.dataTransfer.getData('application/reactflow')
      if (!raw) return

      const nodeDef: PaletteNodeDef = JSON.parse(raw)
      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      // Determine node type: custom nodes are generic, pipeline nodes use agentNode
      const isCustom = nodeDef.id === 'custom'
      const newNode: RFNode = {
        id: `${nodeDef.id}-${Date.now()}`,
        type: isCustom ? 'default' : 'agentNode',
        position,
        data: {
          label: nodeDef.label,
          icon: nodeDef.icon,
          status: 'pending',
          description: nodeDef.description,
        },
      }

      setExtraNodes((prev) => [...prev, newNode])
      if (onNodesUpdate) onNodesUpdate([...nodes, ...extraNodes, newNode])
    },
    [reactFlowInstance, nodes, extraNodes, onNodesUpdate],
  )

  const handleNodesChange = useCallback(
    (changes: any) => {
      onNodesChange(changes)
      // After applying changes, notify parent of new node set
      if (onNodesUpdate) {
        setTimeout(() => onNodesUpdate([...nodes, ...extraNodes]), 0)
      }
    },
    [onNodesChange, onNodesUpdate, nodes, extraNodes],
  )

  const allNodes = useMemo(() => [...nodes, ...extraNodes], [nodes, extraNodes])

  return (
    <div
      className={`w-full h-full ${paletteOpen ? '' : ''}`}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <ReactFlow
        nodes={allNodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onNodeClick?.(node.id)}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.2}
        maxZoom={3}
        className="bg-[#0b0f14]"
        deleteKeyCode={null}
      >
        <Controls
          className="!bg-slate-900 !border-slate-700 [&_button]:!text-slate-400 [&_button:hover]:!text-white"
        />
        <MiniMap
          style={{ background: '#0f172a', border: '1px solid #1e293b' }}
          nodeColor={(node) => STATUS_THEME[(node.data.status as StepStatus)]?.border || '#334155'}
          maskColor="rgba(0,0,0,0.6)"
        />
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e293b" />
      </ReactFlow>
    </div>
  )
}
