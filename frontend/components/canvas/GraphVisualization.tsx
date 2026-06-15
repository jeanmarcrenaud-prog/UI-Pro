'use client';

import React, { useCallback, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  NodeProps,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Play, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';

import { CanvasStep, useAgentCanvasStore } from '@/lib/stores/agentCanvasStore';

const nodeTypes = { agentStep: AgentStepNode };

interface GraphVisualizationProps {
  steps: CanvasStep[];
  onNodeClick?: (nodeId: string) => void;
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'running': return <Play className="w-6 h-6 text-blue-400" />;
    case 'done': return <CheckCircle className="w-6 h-6 text-emerald-400" />;
    case 'error': return <XCircle className="w-6 h-6 text-red-400" />;
    case 'awaiting_approval': return <Clock className="w-6 h-6 text-amber-400" />;
    default: return <Clock className="w-6 h-6 text-gray-500" />;
  }
}

function AgentStepNode({ data, selected }: NodeProps) {
  const step = data as CanvasStep;
  const isActive = step.status === 'running';

  return (
    <motion.div
      whileHover={{ scale: 1.03, y: -4 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={`relative px-6 py-5 rounded-3xl border-2 shadow-2xl min-w-[270px] backdrop-blur-md transition-all
        ${step.status === 'running' ? 'border-blue-500 shadow-blue-500/40' : ''}
        ${step.status === 'done' ? 'border-emerald-500 shadow-emerald-500/20' : ''}
        ${step.status === 'error' ? 'border-red-500 shadow-red-500/30' : ''}
        ${step.status === 'awaiting_approval' ? 'border-amber-500 shadow-amber-500/30' : ''}
        ${selected ? 'ring-2 ring-white/60' : ''}
      `}
    >
      {isActive && (
        <div className="absolute -inset-1 bg-blue-500/20 rounded-3xl -z-10 blur-2xl" />
      )}

      <div className="flex items-start gap-4">
        <motion.div
          animate={isActive ? { rotate: 360 } : {}}
          transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
          className="mt-0.5"
        >
          {getStatusIcon(step.status)}
        </motion.div>

        <div className="flex-1 min-w-0">
          <div className="font-semibold text-lg text-white tracking-tight">{step.name}</div>
          
          {step.modelUsed && (
            <div className="text-xs text-gray-400 font-mono mt-1 truncate">{step.modelUsed}</div>
          )}

          <div className="flex gap-4 mt-4 text-xs text-gray-400 font-mono">
            {step.durationMs && <span>⏱ {Math.round(step.durationMs)}ms</span>}
            {step.tokens && <span>🔤 {step.tokens}</span>}
          </div>
        </div>
      </div>

      {/* Status badge */}
      <div className="absolute top-4 right-4 px-3 py-1 text-[10px] font-mono rounded-full border border-gray-700 bg-gray-950/80">
        {step.status.toUpperCase()}
      </div>
    </motion.div>
  );
}

export default function GraphVisualization({ steps, onNodeClick }: GraphVisualizationProps) {
  const { selectedNodeId, setSelectedNode } = useAgentCanvasStore();

  const nodes: Node[] = useMemo(() => {
    return steps.map((step, index) => ({
      id: step.name,
      type: 'agentStep',
      position: { x: 100, y: index * 160 },
      data: step,
      selected: selectedNodeId === step.name,
    }));
  }, [steps, selectedNodeId]);

  const edges: Edge[] = useMemo(() => {
    return steps.slice(1).map((_, index) => {
      const source = steps[index];
      const target = steps[index + 1];
      const isActive = source.status === 'running' || target.status === 'running';

      return {
        id: `e${source.name}-${target.name}`,
        source: source.name,
        target: target.name,
        type: 'smoothstep',
        animated: isActive,
        style: { 
          stroke: isActive ? '#60a5fa' : '#475569', 
          strokeWidth: 3.5 
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 22,
          height: 22,
          color: isActive ? '#60a5fa' : '#475569'
        },
      };
    });
  }, [steps]);

  const handleNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node.id);
    onNodeClick?.(node.id);
  }, [setSelectedNode, onNodeClick]);

  return (
    <div className="w-full h-full bg-[#0a0e14]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background color="#1e2937" gap={28} />
        <Controls position="bottom-right" className="bg-gray-900 border border-gray-700" />
        <MiniMap 
          position="bottom-left" 
          className="bg-gray-900 border border-gray-700"
          nodeColor={() => '#334155'}
        />
      </ReactFlow>
    </div>
  );
}
