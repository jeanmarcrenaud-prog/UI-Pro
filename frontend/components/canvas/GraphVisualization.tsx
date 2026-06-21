'use client';

import React, { useCallback, useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
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
  'step-analyzing':            { x: 40,  y: 120 },
  'step-planning':             { x: 320, y: 120 },
  'step-coding':               { x: 600, y: 120 },
  'step-reviewing':            { x: 880, y: 120 },
  'step-executing':            { x: 1160, y: 120 },
  'step-fixing':               { x: 880, y: 380 },
  'step-execution_success':    { x: 1440, y: 120 },
  'step-max_attempts_reached': { x: 1440, y: 380 },
  'step-execution_failed':     { x: 1440, y: 380 },
  'step-no_code_short_circuit':{ x: 1440, y: 380 },
};

// Edge definitions: [source, target, isLoopBack]
const EDGE_DEFS: Array<[string, string, boolean]> = [
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
    return steps.map((step, index) => {
      const pos = STEP_POSITIONS[step.name] || { x: 80, y: 120 + (index % 2) * 80 };
      return {
        id: step.name,
        type: 'agentStep',
        position: pos,
        data: step,
        selected: selectedNodeId === step.name,
      };
    });
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
    <div className="agent-canvas w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background color="#1f2937" gap={24} />
        <Controls
          position="bottom-right"
          className="bg-gray-900/95 border border-gray-700 rounded-xl shadow-xl"
        />
      </ReactFlow>
    </div>
  );
}
