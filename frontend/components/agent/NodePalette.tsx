// components/agent/NodePalette.tsx
// Draggable node palette for the Agent Canvas — users drag nodes onto the React Flow graph

'use client'

import { memo } from 'react'

export interface PaletteNodeDef {
  id: string
  label: string
  icon: string
  description: string
  color: string
}

const PALETTE_NODES: PaletteNodeDef[] = [
  { id: 'step-analyzing', label: 'Analyze',     icon: '🔍', description: 'Classify & route task',        color: '#8b5cf6' },
  { id: 'step-planning',  label: 'Plan',        icon: '📋', description: 'Structured implementation plan', color: '#3b82f6' },
  { id: 'step-coding',    label: 'Code',        icon: '⚙️', description: 'Generate Python code',           color: '#f59e0b' },
  { id: 'step-reviewing', label: 'Review',      icon: '👁️', description: 'Static & LLM review',           color: '#10b981' },
  { id: 'step-executing', label: 'Execute',     icon: '▶️', description: 'Sandboxed code execution',        color: '#ef4444' },
  { id: 'custom',         label: 'Custom Node', icon: '➕', description: 'Add a custom annotation node',   color: '#64748b' },
]

interface NodePaletteProps {
  isOpen: boolean
  onClose: () => void
}

function NodePaletteInner({ isOpen, onClose }: NodePaletteProps) {
  const handleDragStart = (event: React.DragEvent, nodeDef: PaletteNodeDef) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeDef))
    event.dataTransfer.effectAllowed = 'move'
  }

  if (!isOpen) return null

  return (
    <div className="w-52 shrink-0 border-r border-slate-700/50 bg-slate-900/80 backdrop-blur-sm flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700/50">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Nodes</span>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-slate-700/50 text-slate-500 hover:text-white transition-colors"
          title="Close palette"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 2l8 8M10 2l-8 8" />
          </svg>
        </button>
      </div>

      {/* Draggable items */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {PALETTE_NODES.map((node) => (
          <div
            key={node.id}
            draggable
            onDragStart={(e) => handleDragStart(e, node)}
            className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-grab active:cursor-grabbing
                       bg-slate-800/40 hover:bg-slate-700/60 border border-transparent hover:border-slate-600/50
                       transition-all duration-150 select-none group"
          >
            <span className="text-base shrink-0">{node.icon}</span>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-slate-300 group-hover:text-white truncate transition-colors">
                {node.label}
              </div>
              <div className="text-[10px] text-slate-500 truncate">{node.description}</div>
            </div>
            {/* Drag indicator */}
            <svg
              width="10" height="10" viewBox="0 0 10 10"
              className="shrink-0 text-slate-600 group-hover:text-slate-400 transition-colors"
            >
              <circle cx="3" cy="3" r="1.5" fill="currentColor" />
              <circle cx="7" cy="3" r="1.5" fill="currentColor" />
              <circle cx="3" cy="7" r="1.5" fill="currentColor" />
              <circle cx="7" cy="7" r="1.5" fill="currentColor" />
            </svg>
          </div>
        ))}
      </div>

      {/* Footer hint */}
      <div className="px-3 py-2 border-t border-slate-700/50">
        <p className="text-[10px] text-slate-600 leading-tight">
          Drag nodes onto the canvas to add them to your pipeline.
        </p>
      </div>
    </div>
  )
}

export const NodePalette = memo(NodePaletteInner)
NodePalette.displayName = 'NodePalette'
