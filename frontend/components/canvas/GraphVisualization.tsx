'use client';

import React, { useCallback, useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  MiniMap,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { CanvasStep, useAgentCanvasStore } from '@/lib/stores/agentCanvasStore'
import CustomNode from '@/components/agent/CustomNode'


interface GraphVisualizationProps {
  steps: CanvasStep[];
  onNodeClick?: (nodeId: string) => void;
}

// Animation variants — module-level constant, never changes

// Horizontal layout positions per step type
const STEP_POSITIONS: Record<string, { x: number; y: number }> = {
  'step-orchestrator':         { x: -100, y: 100 },
  'step-analyzing':            { x: 100, y: 100 },
  'step-planning':             { x: 300, y: 100 },
  'step-coding':               { x: 500, y: 100 },
  'step-reviewing':            { x: 700, y: 100 },
  'step-executing':            { x: 900, y: 100 },
  'step-execution_success':    { x: 1100, y: 100 },
  'step-fixing':               { x: 700, y: 320 },
  'step-execution_failed':     { x: 1100, y: 320 },
  'step-max_attempts_reached': { x: 1020, y: 420 },
  'step-no_code_short_circuit':{ x: 1020, y: 500 },
}

// Edge definitions: [source, target, isLoopBack]
const EDGE_DEFS: Array<[string, string, boolean]> = [
  ['step-orchestrator', 'step-analyzing', false],
  ['step-analyzing', 'step-planning', false],
  ['step-planning', 'step-coding', false],
  ['step-coding', 'step-reviewing', false],
  ['step-reviewing', 'step-executing', false],
  ['step-executing', 'step-execution_success', false],
  ['step-executing', 'step-fixing', false],
  ['step-fixing', 'step-coding', true],
  ['step-fixing', 'step-execution_success', false],
  ['step-fixing', 'step-max_attempts_reached', false],
  ['step-fixing', 'step-execution_failed', false],
  ['step-fixing', 'step-no_code_short_circuit', false],
];
// nodeTypes at module scope. CustomNode is imported from a separate module,
// so it survives StrictMode double-mount AND Turbopack HMR re-evaluation.

const nodeTypes = {
  agentStep: CustomNode,
};

export default function GraphVisualization({ steps, onNodeClick }: GraphVisualizationProps) {
  const { selectedNodeId, setSelectedNode } = useAgentCanvasStore();

  const nodes: Node[] = useMemo(() => {
    let fallbackIndex = 0
    return steps.map((step) => {
      const pos = STEP_POSITIONS[step.name]
      if (!pos) {
        // Unknown step name: stack vertically with 80px spacing
        const fy = 100 + fallbackIndex * 80
        fallbackIndex++
        return {
          id: step.name,
          type: 'agentStep' as const,
          position: { x: 80, y: fy },
          data: step,
          selected: selectedNodeId === step.name,
        }
      }
      return {
        id: step.name,
        type: 'agentStep' as const,
        position: pos,
        data: step,
        selected: selectedNodeId === step.name,
      }
    })
  }, [steps, selectedNodeId]);

  const edges: Edge[] = useMemo(() => {
    const stepNames = steps.map(s => s.name);
    const isRunning = (name: string) => {
      const step = steps.find(s => s.name === name);
      return step?.status === 'running';
    };
    return EDGE_DEFS
      .filter(([source, target]) => stepNames.includes(source) && stepNames.includes(target))
      .map(([source, target, isLoopBack]) => ({
        id: `e${source}-${target}`,
        source,
        target,
        type: isLoopBack ? 'default' : 'smoothstep',
        animated: isRunning(source) || isRunning(target),
        className: isLoopBack ? 'edge-fix-loop' : undefined,
        style: { zIndex: isLoopBack ? 10 : 1 },
      }));
  }, [steps]);

  const handleNodeClick = useCallback(
    (_: any, node: Node) => {
      setSelectedNode(node.id);
      onNodeClick?.(node.id);
    },
    [setSelectedNode, onNodeClick],
  );

  return (
    <div className="agent-canvas w-full h-full relative bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        panOnScroll
        zoomOnScroll
        zoomOnDoubleClick={false}
        minZoom={0.1}
        maxZoom={2.0}
      >
        <Background variant={BackgroundVariant.Dots} color="#334155" gap={24} />
        <MiniMap
          position="bottom-left"
          className="!bg-gray-900/80 !border !border-gray-700 !rounded-lg"
          nodeColor={(n) => n.selected ? '#06b6d4' : '#1e293b'}
          maskColor="rgba(0,0,0,0.3)"
          style={{ width: 140, height: 100 }}
        />
        <Controls
          position="bottom-right"
          className="!bg-gray-900/95 !border !border-gray-700 !rounded-xl !shadow-xl [&_button]:!border-gray-600 [&_button]:hover:!bg-gray-700"
        />
      </ReactFlow>
    </div>
  );
}
