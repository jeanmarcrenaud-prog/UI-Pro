// agentCanvasStore.ts
// Zustand store for Agent Canvas — graph steps, selection, approval, run metadata
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { useAgentStore } from './agentStore'
import type { AgentStep } from '@/lib/types'
// sendCanvasMessage imported lazily inside sendApprovalDecision to avoid circular dep

export type StepStatus = 'pending' | 'running' | 'done' | 'error' | 'awaiting_approval'

export interface CanvasStep {
  name: string
  status: StepStatus
  modelUsed?: string
  durationMs?: number
  tokens?: number
  startedAt?: string
  error?: string
  issuesCount?: number
  suggestionsCount?: number
}

interface CanvasState {
  // Main canvas state
  steps: CanvasStep[]
  currentStep: string | null
  selectedNodeId: string | null
  collapsedNodes: string[]
  isRunning: boolean
  isRunning: boolean

  // Approval status
  approvalStatus: 'PENDING' | 'APPROVED' | 'REJECTED' | null
  approvalReason?: string

  // Run metadata
  runId: string | null
  sessionId: string | null

  // Actions
  setSteps: (steps: CanvasStep[]) => void
  updateStep: (name: string, updates: Partial<CanvasStep>) => void
  addStep: (step: CanvasStep) => void
  setCurrentStep: (stepName: string | null) => void
  setSelectedNode: (nodeId: string | null) => void
  toggleCollapse: (nodeId: string) => void
  setRunning: (isRunning: boolean) => void
  setApprovalStatus: (status: 'PENDING' | 'APPROVED' | 'REJECTED', reason?: string) => void
  resetCanvas: () => void
  set: (partial: Partial<Omit<CanvasState, 'set' | 'setSteps' | 'updateStep' | 'addStep' | 'setCurrentStep' | 'setSelectedNode' | 'toggleCollapse' | 'setRunning' | 'setApprovalStatus' | 'resetCanvas' | 'markStepRunning' | 'markStepDone' | 'markStepError' | 'sendApprovalDecision'>>) => void
  setRunning: (isRunning: boolean) => void
  setRunning: (isRunning: boolean) => void
  setApprovalStatus: (status: 'PENDING' | 'APPROVED' | 'REJECTED', reason?: string) => void
  resetCanvas: () => void
  set: (partial: Partial<Omit<CanvasState, 'set' | 'setSteps' | 'updateStep' | 'addStep' | 'setCurrentStep' | 'setSelectedNode' | 'setRunning' | 'setApprovalStatus' | 'resetCanvas' | 'markStepRunning' | 'markStepDone' | 'markStepError' | 'sendApprovalDecision'>>) => void

  // Helpers
  markStepRunning: (name: string) => void
  markStepDone: (name: string, durationMs?: number, tokens?: number) => void
  markStepError: (name: string, error: string) => void
  sendApprovalDecision: (decision: 'APPROVED' | 'REJECTED', reason?: string) => void
}

export const useAgentCanvasStore = create<CanvasState>()(
  devtools(
    persist(
      (set, get) => ({
        steps: [],
        currentStep: null,
        selectedNodeId: null,
        collapsedNodes: [],
        isRunning: false,
        isRunning: false,
        approvalStatus: null,
        approvalReason: undefined,
        runId: null,
        sessionId: null,

        setSteps: (steps) => set({ steps }),

        updateStep: (name, updates) =>
          set((state) => ({
            steps: state.steps.map((step) =>
              step.name === name ? { ...step, ...updates } : step,
            ),
          })),

        addStep: (step) =>
          set((state) => ({
            steps: [...state.steps, step],
          })),

        setCurrentStep: (stepName) => set({ currentStep: stepName }),

        setSelectedNode: (nodeId) => set({ selectedNodeId: nodeId }),
        toggleCollapse: (nodeId) =>
          set((state) => ({
            collapsedNodes: state.collapsedNodes.includes(nodeId)
              ? state.collapsedNodes.filter((id) => id !== nodeId)
              : [...state.collapsedNodes, nodeId],
          })),
        setRunning: (isRunning) => set({ isRunning }),

        setRunning: (isRunning) => set({ isRunning }),

        setApprovalStatus: (status, reason) =>
          set({ approvalStatus: status, approvalReason: reason }),

        markStepRunning: (name) => {
          get().updateStep(name, { status: 'running' })
          get().setCurrentStep(name)
        },

        markStepDone: (name, durationMs, tokens) => {
          get().updateStep(name, { status: 'done', durationMs, tokens })
        },

        markStepError: (name, error) => {
          get().updateStep(name, { status: 'error', error })
        },

        sendApprovalDecision: async (decision, reason) => {
          // Route through chatService so the execute_decision goes on the SAME
          // WebSocket connection that has the active stream session.
          try {
            const { chatService } = await import('@/services/chatService')
            await chatService.sendExecuteDecision(
              decision === 'APPROVED' ? 'execute' : 'cancel',
              reason,
            )
          } catch (err) {
            console.error('[canvasStore] Failed to send approval decision:', err)
          }
          // Update local state immediately (optimistic)
          set({ approvalStatus: decision, approvalReason: reason ?? undefined })
        },

        resetCanvas: () =>
          set({
            steps: [],
            currentStep: null,
            selectedNodeId: null,
            collapsedNodes: [],
            isRunning: false,
            isRunning: false,
            isRunning: false,
            approvalStatus: null,
            approvalReason: undefined,
            runId: null,
          }),

        set: (partial) => set(partial),
      }),
      {
        name: 'ui-pro-canvas-storage',
        partialize: (state) => ({
          steps: state.steps,
          runId: state.runId,
        }),
      },
    ),
    { name: 'AgentCanvasStore' },
  ),
)

// ── Auto-sync: agentStore steps → canvasStore steps ────────────────
// Replaces the old useEffect-based sync in AgentCanvas.tsx.
// By subscribing at the store level, ALL consumers get updates without manual sync.

function syncStepsFromAgent(agentSteps: AgentStep[]) {
  useAgentCanvasStore.getState().setSteps(
    agentSteps.map((s) => ({
      name: s.id,
      status: s.status === 'active' ? 'running' : (s.status as StepStatus),
      durationMs: s.duration ? s.duration * 1000 : undefined,
      tokens: s.tokens,
      startedAt: undefined,
      error: s.detail,
    })),
  )
}

// Subscribe to future agentStore changes and sync to canvasStore
// agentStore uses plain create() without subscribeWithSelector, so we use (state) => void form
useAgentStore.subscribe((state) => {
  syncStepsFromAgent(state.steps)
})

// Initial sync (agentStore may already have steps at module load time)
const initialSteps = useAgentStore.getState().steps
if (initialSteps.length > 0) {
  syncStepsFromAgent(initialSteps)
}

