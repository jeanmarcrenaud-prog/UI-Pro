// useCanvasActions.ts
// Utility hook wrapping common canvas action sequences
import { useAgentCanvasStore } from './agentCanvasStore'

export const useCanvasActions = () => {
  const store = useAgentCanvasStore()

  return {
    startNewRun: (runId: string, sessionId?: string) => {
      store.resetCanvas()
      store.set({ runId, sessionId, isRunning: true })
    },

    updateFromBackendStep: (stepName: string, status: string, metadata?: Record<string, unknown>) => {
      store.updateStep(stepName, { status: status as any, ...metadata })
    },

    approveExecution: (reason?: string) => {
      store.setApprovalStatus('APPROVED', reason)
    },

    rejectExecution: (reason: string) => {
      store.setApprovalStatus('REJECTED', reason)
    },
  }
}
