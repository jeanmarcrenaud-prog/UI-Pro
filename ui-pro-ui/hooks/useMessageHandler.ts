// useMessageHandler.ts
// Role: Gestion complète des messages WebSocket + events globaux

'use client'

import { useEffect, useCallback, useRef } from 'react'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'
import type { AgentStep } from '@/lib/types'

interface UseMessageHandlerProps {
  assistantMessageIdRef: React.MutableRefObject<string>
  contentRef: React.MutableRefObject<string>
  isStreamActiveRef: React.MutableRefObject<boolean>
  isSendingRef: React.MutableRefObject<boolean>
  updateMessageById: (id: string, updater: (prev: string) => string, status?: string) => void
  updateLastChunkIndex: (index: number) => void
  updateStep: (stepId: string, status: 'pending' | 'active' | 'done') => void
  saveToHistory: () => void
  resetCurrentMessage: () => void
  trimMessageHistory: () => void
  setError: (error: string) => void
  setTokenCount: (count: number) => void
  setCurrentCode: (code: string) => void
  addLog: (message: string) => void
  initialSteps: AgentStep[]
}

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

    // === STEP UPDATES ===
    if (msg.type === 'step' && msg.step_id) {
      const stepName = msg.step_id.replace('step-', '').replace('-', ' ')
      const status = msg.status === 'done' ? 'done' : 'active'
      const content = msg.content || ''
      
      // Log the step event for debug panel
      addLog(`[STEP] ${stepName}: ${content || status}`)
      
      updateStep(msg.step_id, status)
      return
    }

    // === TOKEN STREAMING ===
    const tokenContent = msg.content || msg.delta || ''
    if ((msg.type === 'token' || msg.status === 'streaming') && tokenContent) {
      contentRef.current += tokenContent

      // Compter les tokens
      tokenCountRef.current = estimateTokens(contentRef.current)
      setTokenCount(tokenCountRef.current)

      // Update current code for debug panel
      setCurrentCode(contentRef.current)

      const newIndex = (lastChunkIndexRef.current || 0) + 1
      lastChunkIndexRef.current = newIndex
      updateLastChunkIndex(newIndex)

      updateMessageById(
        assistantMessageIdRef.current,
        (prev) => prev + tokenContent,
        'streaming'
      )
      return
    }

    // === COMPLETION ===
    if (msg.type === 'done' || msg.done === true || msg.status === 'done') {
      isStreamActiveRef.current = false
      isSendingRef.current = false

      updateMessageById(
        assistantMessageIdRef.current,
        () => contentRef.current,
        'done'
      )

      saveToHistory()

      // Marquer toutes les étapes comme terminées
      initialSteps.forEach(step => updateStep(step.id, 'done'))

      resetCurrentMessage()
      trimMessageHistory()
      contentRef.current = ''
      tokenCountRef.current = 0
      setTokenCount(0)
      setCurrentCode('')
    }

    // === ERROR ===
    if (msg.type === 'error') {
      isStreamActiveRef.current = false
      isSendingRef.current = false

      const errorMsg = msg.message || 'Unknown error'
      setError(errorMsg)

      updateMessageById(
        assistantMessageIdRef.current,
        () => errorMsg,
        'error'
      )
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

  // Handler pour les événements globaux agentStep
  const handleAgentStep = useCallback((data: { stepId: string; status: string }) => {
    if (!isStreamActiveRef.current) return

    // Quand un nouveau step devient actif, marquer le précédent comme done
    if (data.status === 'active') {
      const stepOrder = ['step-analyzing', 'step-planning', 'step-executing', 'step-reviewing']
      const currentIdx = stepOrder.indexOf(data.stepId)
      if (currentIdx > 0) {
        const prevStepId = stepOrder[currentIdx - 1]
        updateStep(prevStepId, 'done')
      }
    }

    updateStep(data.stepId, data.status === 'done' ? 'done' : 'active')
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