// agentCanvasStore.ts
// Zustand store for Agent Canvas — graph steps, selection, run metadata
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import { useAgentStore } from './agentStore'
import type { AgentStep } from '@/lib/types'

export type StepStatus = 'pending' | 'running' | 'done' | 'error'

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
  resetCanvas: () => void
  set: (partial: Partial<Omit<CanvasState, 'set' | 'setSteps' | 'updateStep' | 'addStep' | 'setCurrentStep' | 'setSelectedNode' | 'toggleCollapse' | 'setRunning' | 'resetCanvas' | 'markStepRunning' | 'markStepDone' | 'markStepError'>>) => void

  // Helpers
  markStepRunning: (name: string) => void
  markStepDone: (name: string, durationMs?: number, tokens?: number) => void
  markStepError: (name: string, error: string) => void
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


        resetCanvas: () =>
          set({
            steps: [],
            currentStep: null,
            selectedNodeId: null,
            collapsedNodes: [],
            isRunning: false,
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
  const canvasStore = useAgentCanvasStore.getState()
  canvasStore.setSteps(
    agentSteps.map((s) => ({
      name: s.id,
      status: s.status === 'active' ? 'running' : (s.status as StepStatus),
      durationMs: s.duration ? s.duration * 1000 : undefined,
      tokens: s.tokens,
      startedAt: undefined,
      error: s.detail,
    })),
  )
  // Sync execution state so the "live" badge / isRunning reflect
  // the actual streaming state (was never set during streaming).
  const hasActive = agentSteps.some((s) => s.status === 'active')
  const isIdle = agentSteps.length === 0 || agentSteps.every((s) => s.status === 'done' || s.status === 'error')
  if (hasActive) {
    canvasStore.setRunning(true)
  } else if (isIdle) {
    canvasStore.setRunning(false)
  }
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

