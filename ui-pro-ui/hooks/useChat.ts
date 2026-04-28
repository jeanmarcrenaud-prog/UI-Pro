// useChat.ts
// Role: Core React hook for chat with WebSocket resume support

'use client'

import { useCallback, useEffect, useRef } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'
import type { Message } from '@/lib/types'

export const useChat = () => {
  const {
    currentMessageId,
    lastReceivedChunkIndex,
    messageHistory,
    setCurrentMessage,
    updateLastChunkIndex,
    resetCurrentMessage,
    trimMessageHistory,
    getPromptById,
    addMessage,
    updateMessageById,
    setLoading,
    setError,
    saveToHistory,
    messages,
    isLoading,
    error,
  } = useChatStore()

  const { steps, start, updateStep, reset: resetAgent } = useAgentStore()

  // Refs
  const isSendingRef = useRef(false)
  const isStreamActiveRef = useRef(false)
  const contentRef = useRef('')
  const assistantMessageIdRef = useRef('')
  const safetyTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // ===================== RESUME LOGIC =====================
  const attemptResume = useCallback(async () => {
    if (!currentMessageId || lastReceivedChunkIndex <= 0) return

    const originalPrompt = getPromptById(currentMessageId)
    if (!originalPrompt) {
      console.warn('[useChat] Cannot resume: original prompt not found')
      return
    }

    console.log(`[useChat] Attempting resume → messageId: ${currentMessageId}, from chunk: ${lastReceivedChunkIndex}`)

    try {
      await chatService.sendMessage(
        originalPrompt,
        currentMessageId,
        lastReceivedChunkIndex
      )
    } catch (err) {
      console.error('[useChat] Resume failed:', err)
    }
  }, [currentMessageId, lastReceivedChunkIndex, getPromptById])

  // Auto resume when WebSocket goes idle while streaming
  useEffect(() => {
    const handleStatus = (data: { status: string }) => {
      if (data.status === 'idle' && isStreamActiveRef.current && currentMessageId) {
        console.log('[useChat] WebSocket became idle during active stream → triggering resume')
        attemptResume()
      }
    }

    events.on('status', handleStatus)
    return () => events.off('status', handleStatus)
  }, [currentMessageId, attemptResume])

  // ===================== MESSAGE HANDLER =====================
  useEffect(() => {
    const unsubscribe = chatService.onMessage((msg: Message) => {
      if (!isStreamActiveRef.current) return

      // === Step Events ===
      if (msg.type === 'step' && msg.step_id) {
        // Use msg.status to determine step status (not msg.type which is 'step' here)
        const status = (msg.status === 'done') ? 'done' : 'active'
        updateStep(msg.step_id, status)
        return
      }

      // === Token Streaming ===
      if (msg.delta || msg.content) {
        const text = msg.delta || msg.content || ''
        contentRef.current += text

        // Update chunk index
        const newIndex = lastReceivedChunkIndex + 1
        updateLastChunkIndex(newIndex)

        // Update UI message
        updateMessageById(assistantMessageIdRef.current, (prev) => prev + text, 'streaming')
      }

      // === Done ===
      if (msg.status === 'done' || msg.done === true) {
        isStreamActiveRef.current = false
        isSendingRef.current = false

        updateMessageById(assistantMessageIdRef.current, () => contentRef.current, 'done')
        saveToHistory()

        // Force all steps to done
        steps.forEach((step) => {
          if (step.status !== 'done') updateStep(step.id, 'done')
        })

        resetCurrentMessage()
        trimMessageHistory()
        contentRef.current = ''

        if (safetyTimeoutRef.current) {
          clearTimeout(safetyTimeoutRef.current)
          safetyTimeoutRef.current = null
        }
      }

      // === Error ===
      if (msg.status === 'error') {
        isStreamActiveRef.current = false
        isSendingRef.current = false
        setError(msg.content || 'Unknown error')
        updateMessageById(assistantMessageIdRef.current, () => msg.content || '', 'error')

        if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current)
      }
    })

    return () => { unsubscribe() }
  }, [
    updateMessageById,
    updateLastChunkIndex,
    saveToHistory,
    setError,
    steps,
    updateStep,
    resetCurrentMessage,
    lastReceivedChunkIndex,
  ])

  // ===================== SEND MESSAGE =====================
  const sendMessage = useCallback(async (content: string) => {
    if (isSendingRef.current || !content.trim()) return

    // Cleanup previous timeout
    if (safetyTimeoutRef.current) {
      clearTimeout(safetyTimeoutRef.current)
    }

    isSendingRef.current = true
    isStreamActiveRef.current = true
    contentRef.current = ''

    const messageId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    // Save for potential resume
    setCurrentMessage(messageId, content)
    assistantMessageIdRef.current = assistantId

    // Add UI messages
    addMessage({ role: 'user', content, id: crypto.randomUUID() })
    addMessage({
      role: 'assistant',
      content: '',
      status: 'thinking',
      id: assistantId,
    })

    setLoading(true)
    resetAgent()

    // Initialize agent steps
    const initialSteps = [
      { id: 'step-analyzing', title: 'Analyzing request', status: 'pending' as const },
      { id: 'step-planning', title: 'Planning solution', status: 'pending' as const },
      { id: 'step-executing', title: 'Executing', status: 'pending' as const },
      { id: 'step-reviewing', title: 'Reviewing', status: 'pending' as const },
    ]
    start(initialSteps)

    try {
      await chatService.sendMessage(content, messageId, 0) // New message → start from chunk 0

      // Safety timeout (5 minutes)
      safetyTimeoutRef.current = setTimeout(() => {
        if (isStreamActiveRef.current) {
          console.warn('[useChat] Safety timeout triggered (5min)')
          isStreamActiveRef.current = false
          isSendingRef.current = false
          setError('Request timed out')
        }
      }, 300000)

    } catch (err: unknown) {
      console.error('[useChat] Failed to send message:', err)
      const message = err instanceof Error ? err.message : 'Failed to send message'
      setError(message)
      isSendingRef.current = false
      isStreamActiveRef.current = false
    }
  }, [
    addMessage,
    setLoading,
    setError,
    start,
    resetAgent,
    setCurrentMessage,
  ])

  // ===================== CANCEL & CLEAR =====================
  const cancel = useCallback(() => {
    chatService.cancel()
    isStreamActiveRef.current = false
    isSendingRef.current = false
    if (safetyTimeoutRef.current) {
      clearTimeout(safetyTimeoutRef.current)
      safetyTimeoutRef.current = null
    }
  }, [])

  const clear = useCallback(() => {
    cancel()
    resetCurrentMessage()
    trimMessageHistory()
    contentRef.current = ''
  }, [cancel, resetCurrentMessage, trimMessageHistory])

  return {
    messages,
    isLoading,
    error,
    steps,
    currentStep: steps.find((s) => s.status === 'active'),
    sendMessage,
    cancel,
    clear,
  }
}