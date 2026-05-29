// agentStore.ts
// Role: Agent execution state store via Zustand - tracks active status, step list and individual step
// status updates, current step tracking, and agent lifecycle (start/reset)

import { create } from 'zustand'
import type { AgentStep, AgentStepStatus } from '@/lib/types'

interface AgentStore {
  isActive: boolean
  steps: AgentStep[]
  currentStep: number
  currentStepId?: string
  addStep: (step: AgentStep) => void
  updateStep: (id: string, status: AgentStepStatus, detail?: string) => void
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

  updateStep: (id, status, detail) =>
    set((state) => {
      const stepIdx = state.steps.findIndex(s => s.id === id)
      const currentStep = state.steps[stepIdx]
      
      // Don't allow status to go backwards (done -> active)
      if (currentStep && currentStep.status === 'done' && status !== 'done') {
        return state
      }
      
      // If step doesn't exist, add it
      if (stepIdx === -1) {
        return {
          steps: [...state.steps, { id, title: id.replace('step-', '').replace('-', ' '), status, detail }],
          currentStepId: id,
          currentStep: state.steps.length
        }
      }
      
      return {
        steps: state.steps.map((s) =>
          s.id === id ? { ...s, status, detail: detail ?? s.detail } : s
        ),
        currentStepId: id,
        currentStep: stepIdx
      }
    }),

  setStep: (step, index) =>
    set((state) => {
      const newSteps = [...state.steps]
      newSteps[index] = step
      return { steps: newSteps, currentStep: index, currentStepId: step.id }
    }),

  setSteps: (steps) => set({ steps, currentStep: 0, currentStepId: steps[0]?.id }),

  reset: () => set({ isActive: false, steps: [], currentStep: 0, currentStepId: undefined }),

  start: (steps) => {
    const activeStep = steps.find(s => s.status === 'active')
    set({ 
      isActive: true, 
      steps, 
      currentStep: 0, 
      currentStepId: activeStep?.id 
    })
  },

  getActiveStep: () => {
    const state = _get()
    return state.steps.find(s => s.status === 'active')
  },
}))

export const agentStore = {
  getState: () => useAgentStore.getState(),
}