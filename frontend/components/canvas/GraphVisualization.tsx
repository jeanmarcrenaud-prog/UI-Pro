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
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Play, CheckCircle, XCircle, Clock } from 'lucide-react';
import { motion } from 'framer-motion';

import { CanvasStep, useAgentCanvasStore } from '@/lib/stores/agentCanvasStore';

const nodeTypes = { agentStep: AgentStepNode };

interface GraphVisualizationProps {
  steps: CanvasStep[];
  onNodeClick?: (nodeId: string) => void;
}

function AgentStepNode({ data, selected }: NodeProps) {
  const step = data as CanvasStep;
  const isActive = step.status === 'running';
  const isFixNode = step.name === 'Fix Code';

  return (
    <motion.div
      initial={{ scale: 0.88, opacity: 0, y: 20 }}
      animate={{ scale: 1, opacity: 1, y: 0 }}
      whileHover={{ scale: 1.04, y: -8 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={`relative px-6 py-5 rounded-3xl border-2 shadow-2xl min-w-[275px] backdrop-blur-md overflow-hidden
        ${isActive ? 'border-amber-500 shadow-amber-500/50' : ''}
        ${step.status === 'done' ? 'border-emerald-500' : ''}
        ${step.status === 'error' ? 'border-red-500' : ''}
        ${step.status === 'awaiting_approval' ? 'border-amber-500 shadow-amber-500/40' : ''}
        ${isFixNode && step.status === 'running' ? 'border-amber-500 shadow-amber-500/50' : ''}
        ${selected ? 'ring-2 ring-offset-2 ring-offset-[#0a0e14] ring-white/70' : ''}
      `}
    >
      <Handle type="target" position={Position.Top} className="!bg-transparent !border-0" />
      <Handle type="target" position={Position.Right} id="right" className="!bg-transparent !border-0" />

      {isActive && (
        <motion.div 
          className="absolute -inset-3 bg-amber-500/20 rounded-3xl -z-10 blur-3xl"
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 2.5, repeat: Infinity }}
        />
      )}

      <div className="flex items-start gap-4">
        <motion.div
          animate={isActive ? { rotate: 360 } : {}}
          transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
        >
          {getStatusIcon(step.status)}
        </motion.div>

        <div className="flex-1 min-w-0">
          <div className="font-semibold text-lg text-white tracking-tight">{step.name}</div>
          {isFixNode && step.attempt && step.maxAttempts && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30">
                attempt {step.attempt}/{step.maxAttempts}
              </span>
            </div>
          )}
          {step.modelUsed && (
            <div className="text-xs text-gray-400 font-mono mt-1">{step.modelUsed}</div>
          )}
          <div className="mt-3 flex gap-4 text-xs text-gray-400 font-mono">
            {step.durationMs && <span>⏱ {Math.round(step.durationMs)}ms</span>}
            {step.tokens && <span>🔤 {step.tokens}</span>}
          </div>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-0" />
      <Handle type="source" position={Position.Right} id="right" className="!bg-transparent !border-0" />
    </motion.div>
  );
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

export default function GraphVisualization({ steps, onNodeClick }: GraphVisualizationProps) {
  const { selectedNodeId, setSelectedNode } = useAgentCanvasStore();

  const nodes = useMemo(() => {
    return steps.map((step, index) => ({
      id: step.name,
      type: 'agentStep',
      position: { x: 140, y: index * 175 },
      data: step,
      selected: selectedNodeId === step.name,
    }));
  }, [steps, selectedNodeId]);

  const edges = useMemo(() => {
    const result: Edge[] = steps.slice(1).map((_, i) => {
      const sourceStep = steps[i];
      const targetStep = steps[i + 1];
      const isFlowing = sourceStep.status === 'running';

      return {
        id: `e${sourceStep.name}-${targetStep.name}`,
        source: sourceStep.name,
        target: targetStep.name,
        type: 'smoothstep',
        animated: isFlowing,
        style: { 
          stroke: isFlowing ? '#60a5fa' : '#475569', 
          strokeWidth: 4,
          strokeDasharray: targetStep.status === 'pending' ? '10 5' : 'none'
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 26,
          height: 26,
          color: isFlowing ? '#60a5fa' : '#475569'
        },
      };
    });

    // Fix loop edge: Fix Code → Code (right-side loop)
    const fixStep = steps.find(s => s.name === 'Fix Code');
    if (fixStep) {
      result.push({
        id: 'eFixLoop-Code',
        source: 'Fix Code',
        sourceHandle: 'right',
        target: 'Code',
        targetHandle: 'right',
        type: 'smoothstep',
        animated: fixStep.status === 'running',
        style: {
          stroke: '#f59e0b',
          strokeWidth: 4,
          strokeDasharray: '8 4',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 26,
          height: 26,
          color: '#f59e0b',
        },
      });
    }

    return result;
  }, [steps]);

  const handleNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node.id);
    onNodeClick?.(node.id);
  }, [setSelectedNode, onNodeClick]);

  return (
    <div className="w-full h-full bg-[#0a0e14] relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        nodesDraggable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e2937" gap={28} />
        <Controls position="bottom-right" className="bg-gray-900 border border-gray-700" />
        <MiniMap 
          position="bottom-left" 
          className="bg-gray-900 border border-gray-700"
          nodeColor={(node) => {
            const step = steps.find(s => s.name === node.id);
            if (step?.status === 'running') return '#3b82f6';
            if (step?.status === 'done') return '#10b981';
            if (step?.status === 'error') return '#ef4444';
            return '#64748b';
          }}
        />
      </ReactFlow>
    </div>
  );
}
