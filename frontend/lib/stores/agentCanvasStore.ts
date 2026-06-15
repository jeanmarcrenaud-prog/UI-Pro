// agentCanvasStore.ts
// Store for the ReactFlow-based Agent Canvas graph visualization

import { create } from 'zustand'

export interface CanvasStep {
  name: string
  status: 'pending' | 'running' | 'done' | 'error' | 'awaiting_approval'
  modelUsed?: string
  durationMs?: number
  tokens?: number
}

interface AgentCanvasStore {
  selectedNodeId: string | null
  setSelectedNode: (id: string | null) => void
}

export const useAgentCanvasStore = create<AgentCanvasStore>((set) => ({
  selectedNodeId: null,
  setSelectedNode: (id) => set({ selectedNodeId: id }),
}))
