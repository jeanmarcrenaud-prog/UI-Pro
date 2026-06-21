'use client';

import React, { useCallback, useMemo } from 'react';
import ReactFlow, {
  Handle,
  Position,
  Node,
  Edge,
  Controls,
  Background,
  NodeProps,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Play, CheckCircle, XCircle, Clock } from 'lucide-react';
import { motion } from 'framer-motion';

import { CanvasStep, useAgentCanvasStore } from '@/lib/stores/agentCanvasStore';

interface GraphVisualizationProps {
  steps: CanvasStep[];
  onNodeClick?: (nodeId: string) => void;
}

// Animation variants — module-level constant, never changes
const nodeVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.95 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      delay: i * 0.08,
      duration: 0.4,
      ease: [0.23, 1.0, 0.32, 1.0] as const,
    },
  }),
  statusChange: {
    scale: [1, 1.05, 1],
    transition: { duration: 0.3 },
  },
};

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
// AgentStepNode at module scope — const arrow function gives a STABLE reference
// across module re-evaluations (Turbopack HMR). Unlike function declarations,
// const arrow functions are NOT re-created on each module evaluation.
function AgentStepNode({ data, selected, id }: NodeProps) {
  const { status, name, modelUsed, durationMs, tokens } = data as CanvasStep;

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <Play className="w-5 h-5 text-blue-500 animate-pulse" />;
      case 'done':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'awaiting_approval':
        return <Clock className="w-5 h-5 text-amber-500" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getNodeClasses = () => {
    const typeMap: Record<string, string> = {
      'step-analyzing': 'node-analyzing',
      'step-planning': 'node-planning',
      'step-coding': 'node-coding',
      'step-reviewing': 'node-reviewing',
      'step-executing': 'node-executing',
      'step-fixing': 'node-fix',
    };

    let cls = 'canvas-node';
    cls += ' ' + (typeMap[name] || '');

    if (status === 'done') cls += ' node-completed node-success';
    else if (status === 'error') cls += ' node-error';
    else if (status === 'pending') cls += ' node-waiting';

    if (status === 'running') cls += ' node-active';

    if (id?.includes('progress') || id?.includes('orchestrator')) {
      cls += ' node-step-progress';
    }

    return cls;
  };
  return (
    <motion.div
      className={`${getNodeClasses()} ${
        selected ? 'ring-2 ring-white/70' : ''
      }`}
      variants={nodeVariants}
      initial="hidden"
      animate="visible"
      whileHover={{ scale: 1.02, transition: { duration: 0.2 } }}
      whileTap={{ scale: 0.98 }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !border-2 !border-gray-600 !bg-gray-900"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !border-2 !border-gray-600 !bg-gray-900"
      />

      <div className="flex items-center gap-3">
        <motion.div
          animate={status === 'running' ? { rotate: 360 } : {}}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
        >
          {getStatusIcon()}
        </motion.div>

        <div className="flex-1">
          <div className="font-semibold text-white text-base tracking-tight">{name}</div>
          {modelUsed && (
            <div className="text-xs text-gray-400 mt-0.5 font-mono">{modelUsed}</div>
          )}
        </div>
      </div>

      {(durationMs || tokens) && (
        <motion.div
          className="mt-3 text-xs text-gray-400 flex gap-4 font-mono"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          {durationMs && <span>⏱ {Math.round(durationMs)}ms</span>}
          {tokens && <span>🔤 {tokens} tokens</span>}
        </motion.div>
      )}
    </motion.div>
  );
}

// nodeTypes at module scope — created ONCE at module load time.
// This is the ONLY pattern that survives StrictMode double-mount
// AND Turbopack module re-evaluation without triggering the warning.
const nodeTypes = {
  agentStep: AgentStepNode,
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
