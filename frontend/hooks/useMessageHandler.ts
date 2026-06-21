// useMessageHandler.ts
// Role: Gestion complète des messages WebSocket + events globaux

'use client'

import { useEffect, useCallback, useRef } from 'react'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'
import { normalizeMessage } from '@/lib/messageAdapter'
import { debugLogger } from '@/lib/debug/logger'
import type { AgentStep, Message, MessageStatus } from '@/lib/types'
import { useAgentStore } from '@/lib/stores/agentStore'

interface UseMessageHandlerProps {
  assistantMessageIdRef: React.MutableRefObject<string>
  contentRef: React.MutableRefObject<string>
  isStreamActiveRef: React.MutableRefObject<boolean>
  isSendingRef: React.MutableRefObject<boolean>
  updateMessageById: (id: string, updater: (prev: string) => string, status?: MessageStatus) => void
  updateLastChunkIndex: (index: number) => void
  updateStep: (stepId: string, status: 'pending' | 'active' | 'done', content?: string, duration?: number, tokens?: number, attempt?: number, maxAttempts?: number) => void
  saveToHistory: () => void
  resetCurrentMessage: () => void
  trimMessageHistory: () => void
  setError: (error: string) => void
  setTokenCount: (count: number) => void
  setCurrentCode: (code: string) => void
  addLog: (message: string) => void
  initialSteps: AgentStep[]
}

const STEP_ORDER = ['step-analyzing', 'step-planning', 'step-coding', 'step-reviewing', 'step-executing'] as const

export const useMessageHandler = ({
  assistantMessageIdRef,
  contentRef,
  isStreamActiveRef,
  isSendingRef,
  updateMessageById,
  updateLastChunkIndex,
  updateStep,
  saveToHistory,
  resetCurrentMessage,
  trimMessageHistory,
  setError,
  setTokenCount,
  setCurrentCode,
  addLog,
  initialSteps,
}: UseMessageHandlerProps) => {

  const lastChunkIndexRef = useRef(0)
  const tokenCountRef = useRef(0)

  // Estimation tokens: ~1 token per 4 caractères
  const estimateTokens = (text: string): number => {
    return Math.ceil(text.length / 4)
  }

  // Handler principal pour les messages du chatService
  const handleMessage = useCallback((msg: any) => {
    if (!isStreamActiveRef.current) {
      return
    }

    // Normalize message to unified format
    const normalized = normalizeMessage(msg)

    // === STEP UPDATES ===
    if (normalized.type === 'step' && normalized.stepId) {
      const stepName = normalized.stepId.replace('step-', '').replace('-', ' ')
      addLog(`[STEP] ${stepName}: ${normalized.content || normalized.status}`)
      debugLogger.log('step', normalized.content ?? normalized.status ?? '', { step: stepName, duration: normalized.duration })
      // If duration is present, this is a node-completion event from @_timed_node
      const status = normalized.duration ? 'done' : (normalized.status === 'done' ? 'done' : 'active')
      updateStep(normalized.stepId, status, normalized.content, normalized.duration, normalized.tokenCount, normalized.attempt, normalized.maxAttempts)
      return
    }

    // === TOKEN STREAMING ===
    if (normalized.type === 'token' && normalized.content) {
      contentRef.current += normalized.content
      debugLogger.logToken(normalized.content)

      // Use real token count if provided, otherwise estimate
      if (normalized.tokenCount !== undefined) {
        tokenCountRef.current = normalized.tokenCount
      } else {
        tokenCountRef.current = estimateTokens(contentRef.current)
      }
      setTokenCount(tokenCountRef.current)

      // Update current code for debug panel
      setCurrentCode(contentRef.current)

      const newIndex = lastChunkIndexRef.current + 1
      lastChunkIndexRef.current = newIndex
      updateLastChunkIndex(newIndex)

      updateMessageById(
        assistantMessageIdRef.current,
        (prev) => prev + normalized.content,
        'streaming'
      )
      return
    }

    // === COMPLETION ===
    if (normalized.type === 'done') {
      isStreamActiveRef.current = false
      isSendingRef.current = false

      updateMessageById(
        assistantMessageIdRef.current,
        () => contentRef.current,
        'done'
      )

      saveToHistory()

      // Марку all steps as done
      initialSteps.forEach(step => updateStep(step.id, 'done'))

      resetCurrentMessage()
      trimMessageHistory()

      // Cleanup refs
      contentRef.current = ''
      tokenCountRef.current = 0
      lastChunkIndexRef.current = 0
      setTokenCount(0)
      setCurrentCode('')
      return
    }

    // === ERROR ===
    if (normalized.type === 'error') {
      isStreamActiveRef.current = false
      isSendingRef.current = false

      const errorMsg = normalized.content || normalized.code || 'Unknown error'
      setError(errorMsg)

      updateMessageById(
        assistantMessageIdRef.current,
        () => errorMsg,
        'error'
      )
      return
    }

    // === FALLBACK: Log unexpected message types ===
    if (normalized.type !== 'unknown') {
      addLog(`[DEBUG] Unhandled message type: ${normalized.type}`)
    }
  }, [
    assistantMessageIdRef,
    contentRef,
    isStreamActiveRef,
    isSendingRef,
    updateMessageById,
    updateLastChunkIndex,
    updateStep,
    saveToHistory,
    resetCurrentMessage,
    trimMessageHistory,
    setError,
    setTokenCount,
    setCurrentCode,
    addLog,
    initialSteps,
  ])

  // Tracks the last step that was activated (not cleared on completion)
  // so we can detect stale state-based events that arrive after @_timed_node
  // completion events (which would incorrectly reactivate a done step).
  const lastActiveStepRef = useRef<string | null>(null)

  const handleAgentStep = useCallback((data: { stepId: string; status: string; content?: string; duration?: number; tokenCount?: number }) => {
    if (!isStreamActiveRef.current) return

    // If duration is present, this is a node-completion event from @_timed_node
    // → mark as done. Otherwise use the event status.
    const stepStatus: 'done' | 'active' = data.duration ? 'done' : (data.status === 'done' ? 'done' : 'active')

    if (stepStatus === 'active') {
      // If this step was the last one activated and is already done in the store,
      // the event is a stale state-based emission after @_timed_node completion.
      // Update the detail/content but don't revert status.
      if (lastActiveStepRef.current === data.stepId) {
        const store = useAgentStore.getState()
        const existingStep = store.steps.find(s => s.id === data.stepId)
        if (existingStep?.status === 'done') {
          // Stale state-based event — update detail only, keep status as done
          updateStep(data.stepId, 'done', data.content)
          return
        }
      }

      // Genuine activation: auto-complete the previously active step
      if (lastActiveStepRef.current && lastActiveStepRef.current !== data.stepId) {
        updateStep(lastActiveStepRef.current, 'done')
      }
      lastActiveStepRef.current = data.stepId
    }
    // Don't clear lastActiveStepRef on completion — keep it for stale detection above

    updateStep(data.stepId, stepStatus, data.content, data.duration, data.tokenCount)
  }, [updateStep, isStreamActiveRef])

  // Configuration des listeners
  useEffect(() => {
    const unsubscribeChat = chatService.onMessage(handleMessage)
    events.on('agentStep', handleAgentStep)

    return () => {
      unsubscribeChat()
      events.off('agentStep', handleAgentStep)
    }
  }, [handleMessage, handleAgentStep])
}