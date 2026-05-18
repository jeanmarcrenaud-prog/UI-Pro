// lib/debug/logger.ts
// Role: Debug logging helpers for the Debug Panel

import { useUIStore } from '@/lib/stores/uiStore'

/**
 * Helpers de logging pour le Debug Panel
 * Centralise tous les logs pour maintenir une cohérence
 */

export interface LogOptions {
  step?: string
  duration?: number
  tokens?: number
}

// ==================== CORE LOGGERS ====================

export const debugLogger = {
  /**
   * Log générique
   */
  log: (type: 'step' | 'token' | 'tool' | 'error' | 'info', content: string, options: LogOptions = {}) => {
    const { addDebugLog } = useUIStore.getState()
    
    addDebugLog({
      type,
      content,
      step: options.step,
      duration: options.duration,
      tokens: options.tokens,
    })
  },

  /**
   * Log d'étape agent (le plus utilisé)
   */
  logStep: (stepName: string, content: string, options: LogOptions = {}) => {
    debugLogger.log('step', content, { ...options, step: stepName })
  },

  /**
   * Log de token streaming
   */
  logToken: (content: string, tokensCount?: number) => {
    debugLogger.log('token', content, { tokens: tokensCount })
  },

  /**
   * Log d'outil / tool call
   */
  logTool: (toolName: string, content: string, duration?: number) => {
    debugLogger.log('tool', content, { 
      step: toolName, 
      duration 
    })
  },

  /**
   * Log d'erreur
   */
  logError: (content: string, error?: any) => {
    const message = error 
      ? `${content}: ${error.message || error}` 
      : content
    
    debugLogger.log('error', message)
    console.error('[DEBUG ERROR]', content, error)
  },

  /**
   * Log d'information
   */
  logInfo: (content: string, step?: string) => {
    debugLogger.log('info', content, { step })
  },

  /**
   * Mise à jour du statut d'une étape (progression)
   */
  updateStepStatus: (
    stepId: string, 
    status: 'pending' | 'active' | 'completed' | 'error',
    data?: { description?: string; duration?: number; progress?: number }
  ) => {
    const { updateStep } = useUIStore.getState()
    updateStep(stepId, { status, ...data })
  },

  /**
   * Remplacer tout le pipeline d'étapes
   */
  setAgentSteps: (steps: Array<{
    id: string
    name: string
    status: 'pending' | 'active' | 'completed' | 'error'
    description?: string
  }>) => {
    const { setAgentSteps } = useUIStore.getState()
    setAgentSteps(steps)
  },

  /**
   * Nettoyer tout
   */
  clearAll: () => {
    const { clearDebugLogs, clearAgentSteps } = useUIStore.getState()
    clearDebugLogs()
    clearAgentSteps()
  }
}

// ==================== CONVENIENCE EXPORTS ====================

export const {
  logStep,
  logToken,
  logTool,
  logError,
  logInfo,
  updateStepStatus,
  setAgentSteps,
  clearAll
} = debugLogger

export default debugLogger