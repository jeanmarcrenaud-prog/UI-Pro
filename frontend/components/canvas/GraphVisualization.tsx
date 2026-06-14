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
import { Play, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

import { CanvasStep, useAgentCanvasStore } from '@/lib/stores/agentCanvasStore';

const nodeTypes = {
  agentStep: AgentStepNode,
};

interface GraphVisualizationProps {
  steps: CanvasStep[];
  onNodeClick?: (nodeId: string) => void;
}

// Animation variants
const nodeVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.95 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      delay: i * 0.08,
      duration: 0.4,
      ease: [0.23, 1.0, 0.32, 1.0],
    },
  }),
  statusChange: {
    scale: [1, 1.05, 1],
    transition: { duration: 0.3 },
  },
};

function AgentStepNode({ data, selected }: NodeProps) {
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

  const getStatusColor = () => {
    switch (status) {
      case 'running': return 'border-blue-500 bg-blue-950/60';
      case 'done': return 'border-green-500 bg-green-950/40';
      case 'error': return 'border-red-500 bg-red-950/40';
      case 'awaiting_approval': return 'border-amber-500 bg-amber-950/40';
      default: return 'border-gray-700 bg-gray-900/80';
    }
  };

  return (
    <motion.div
      className={`px-5 py-4 rounded-2xl border-2 shadow-2xl min-w-[240px] backdrop-blur-sm ${getStatusColor()} ${
        selected ? 'ring-2 ring-white/70 shadow-blue-500/30' : ''
      }`}
      variants={nodeVariants}
      initial="hidden"
      animate="visible"
      whileHover={{ scale: 1.02, transition: { duration: 0.2 } }}
      whileTap={{ scale: 0.98 }}
    >
      {/* Connection handles */}
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
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
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

export default function GraphVisualization({ steps, onNodeClick }: GraphVisualizationProps) {
  const { selectedNodeId, setSelectedNode } = useAgentCanvasStore();

  const nodes: Node[] = useMemo(() => {
    return steps.map((step, index) => ({
      id: step.name,
      type: 'agentStep',
      position: { x: 80, y: index * 140 },
      data: step,
      selected: selectedNodeId === step.name,
    }));
  }, [steps, selectedNodeId]);

  const edges: Edge[] = useMemo(() => {
    return steps.slice(1).map((_, index) => ({
      id: `e${steps[index].name}-${steps[index + 1].name}`,
      source: steps[index].name,
      target: steps[index + 1].name,
      type: 'smoothstep',
      animated: steps[index].status === 'running' || steps[index + 1].status === 'running',
      style: { 
        stroke: steps[index].status === 'running' ? '#60a5fa' : '#4b5563', 
        strokeWidth: 2.5 
      },
    }));
  }, [steps]);

  const handleNodeClick = useCallback(
    (_: any, node: Node) => {
      setSelectedNode(node.id);
      onNodeClick?.(node.id);
    },
    [setSelectedNode, onNodeClick]
  );

  return (
    <div className="w-full h-full bg-[#0a0e14] relative">
      <AnimatePresence>
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
      </AnimatePresence>
    </div>
  );
}
