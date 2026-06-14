// agentCanvasStore.ts
// Zustand store for Agent Canvas — graph steps, selection, approval, run metadata
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
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
