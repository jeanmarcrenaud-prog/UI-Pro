// Agent Store - Zustand
import { create } from 'zustand'
import type { AgentStep } from '@/lib/types'

interface AgentStore {
  isActive: boolean
  steps: AgentStep[]
  currentStep: number
  addStep: (step: AgentStep) => void
  updateStep: (id: string, status: AgentStep['status']) => void
  setStep: (step: AgentStep, index: number) => void
  reset: () => void
  start: (steps: AgentStep[]) => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  isActive: false,
  steps: [],
  currentStep: 0,

  addStep: (step) =>
    set((state) => ({
      steps: [...state.steps, step],
    })),

  updateStep: (id, status) =>
    set((state) => ({
      steps: state.steps.map((s) =>
        s.id === id ? { ...s, status } : s
      ),
    })),

  setStep: (step, index) =>
    set((state) => {
      const newSteps = [...state.steps]
      newSteps[index] = step
      return { steps: newSteps, currentStep: index }
    }),

  reset: () => set({ isActive: false, steps: [], currentStep: 0 }),

  start: (steps) => set({ isActive: true, steps, currentStep: 0 }),
}))
