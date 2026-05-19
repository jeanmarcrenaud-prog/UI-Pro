// infrastructure/persistence/AgentStore.ts
// Role: Agent execution state store via Zustand

import { create } from 'zustand'
import type { AgentStep, AgentStepStatus } from '@/domain/entities'

interface AgentStore {
  isActive: boolean
  steps: AgentStep[]
  currentStep: number
  currentStepId?: string
  addStep: (step: AgentStep) => void
  updateStep: (id: string, status: AgentStepStatus) => void
  setStep: (step: AgentStep, index: number) => void
  setSteps: (steps: AgentStep[]) => void
  reset: () => void
  start: (steps: AgentStep[]) => void
  getActiveStep: () => AgentStep | undefined
}

export const useAgentStore = create<AgentStore>((set, _get) => ({
  isActive: false,
  steps: [],
  currentStep: 0,

  addStep: (step) =>
    set((state) => ({
      steps: [...state.steps, step],
    })),

  updateStep: (id, status) =>
    set((state) => {
      const stepIdx = state.steps.findIndex((s) => s.id === id)
      const currentStep = state.steps[stepIdx]

      if (currentStep && currentStep.status === 'done' && status !== 'done') {
        console.log(
          '[agentStore] Ignoring backwards status update:',
          id,
          currentStep.status,
          '->',
          status
        )
        return state
      }

      return {
        steps: state.steps.map((s) => (s.id === id ? { ...s, status } : s)),
        currentStepId: id,
        currentStep: stepIdx !== -1 ? stepIdx : state.currentStep,
      }
    }),

  setStep: (step, index) =>
    set((state) => {
      const newSteps = [...state.steps]
      newSteps[index] = step
      return { steps: newSteps, currentStep: index, currentStepId: step.id }
    }),

  setSteps: (steps) =>
    set({ steps, currentStep: 0, currentStepId: steps[0]?.id }),

  reset: () =>
    set({ isActive: false, steps: [], currentStep: 0, currentStepId: undefined }),

  start: (steps) => {
    const activeStep = steps.find((s) => s.status === 'active')
    set({
      isActive: true,
      steps,
      currentStep: 0,
      currentStepId: activeStep?.id,
    })
  },

  getActiveStep: () => {
    const state = _get()
    return state.steps.find((s) => s.status === 'active')
  },
}))

export const agentStore = {
  getState: () => useAgentStore.getState(),
}
