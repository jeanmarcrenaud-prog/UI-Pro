// Agent Store - Zustand
import { create } from 'zustand'
import type { AgentStep, AgentStepStatus } from '@/lib/types'

interface AgentStore {
  isActive: boolean
  steps: AgentStep[]
  currentStep: number
  currentStepId?: string // Add current step ID
  addStep: (step: AgentStep) => void
  updateStep: (id: string, status: AgentStepStatus) => void
  setStep: (step: AgentStep, index: number) => void
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
      const stepIdx = state.steps.findIndex(s => s.id === id)
      return {
        steps: state.steps.map((s) =>
          s.id === id ? { ...s, status } : s
        ),
        currentStepId: id,
        currentStep: stepIdx !== -1 ? stepIdx : state.currentStep
      }
    }),

  setStep: (step, index) =>
    set((state) => {
      const newSteps = [...state.steps]
      newSteps[index] = step
      return { steps: newSteps, currentStep: index, currentStepId: step.id }
    }),

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
