// useChat.ts
// Role: Core React hook for chat functionality - orchestrates message sending via WebSocket, manages
// streaming state, agent step lifecycle, error handling, safety timeouts, and token count tracking
// Includes auto-reconnect with resume support

'use client'

import { useCallback, useEffect, useRef } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'
import type { Message, AgentStep, UseChatReturn } from '@/lib/types'

function generateId(): string {
  return crypto.randomUUID()
}

export const useChat = (): UseChatReturn => {
  const {
    messages,
    isLoading,
    error,
    addMessage,
    updateMessageById,
    clearMessages,
    setLoading,
    setError,
    saveToHistory,
    // Resume state
    currentMessageId,
    lastReceivedChunkIndex,
    setCurrentMessage,
    updateLastChunkIndex,
    resetCurrentMessage,
    getPromptById,
  } = useChatStore()

  const { isActive, steps, start, updateStep, reset } = useAgentStore()

  // =====================
  // STATE REFS
  // =====================
  const isSendingRef = useRef(false)
  const isStreamActiveRef = useRef(false)
  const isCompletedRef = useRef(false)

  const currentRequestIdRef = useRef('')
  const assistantMessageIdRef = useRef('')
  const contentRef = useRef('')

  const rafRef = useRef<number | null>(null)
  const safetyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handlerCleanupRef = useRef<(() => void) | null>(null)
  const isMountedRef = useRef(true)

  const updateStepRef = useRef(updateStep)
  updateStepRef.current = updateStep

  // =====================
  // RESUME TRACKING
  // =====================
  const streamIndexRef = useRef(0)

  // Track chunk index from incoming messages
  useEffect(() => {
    const unsubscribe = chatService.onMessage((msg: Message) => {
      if (msg.status === 'streaming' && msg.delta) {
        streamIndexRef.current += 1
        updateLastChunkIndex(streamIndexRef.current)
      }

      if (msg.status === 'done') {
        resetCurrentMessage()
        streamIndexRef.current = 0
      }
    })

    // chatService.onMessage returns () => boolean, but useEffect needs void
    return () => { unsubscribe() }
  }, [updateLastChunkIndex, resetCurrentMessage])

  // Listen for status changes (reconnection detection)
  useEffect(() => {
    const handleStatus = (data: { status: string }) => {
      if (data.status === 'idle' && isStreamActiveRef.current && currentMessageId) {
        console.log('[useChat] Reconnection detected, attempting resume...')
        attemptResume()
      }
    }

    events.on('status', handleStatus)
    return () => events.off('status', handleStatus)
  }, [currentMessageId])

  // Attempt to resume after reconnection
  const attemptResume = useCallback(async () => {
    if (!currentMessageId || lastReceivedChunkIndex === 0) return

    const originalPrompt = getPromptById(currentMessageId)
    if (!originalPrompt) {
      console.log('[useChat] No prompt found for resume')
      return
    }

    console.log('[useChat] Attempting resume:', {
      messageId: currentMessageId,
      chunkIndex: lastReceivedChunkIndex,
      prompt: originalPrompt.slice(0, 30) + '...'
    })

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

  // =====================
  // STOP STREAM (centralisé)
  // =====================
  const stopStream = useCallback(() => {
    isStreamActiveRef.current = false
    isSendingRef.current = false

    setLoading(false)

    handlerCleanupRef.current?.()
    handlerCleanupRef.current = null

    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = null

    if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current)
    safetyTimeoutRef.current = null
  }, [setLoading])

  // =====================
// STEP EVENTS (safe)
  useEffect(() => {
    const handler = (data: {
      stepId: string
      status: 'pending' | 'active' | 'done'
    }) => {
      updateStepRef.current(data.stepId, data.status)
    }

    events.on('agentStep', handler)

    return () => {
      isMountedRef.current = false
      events.off('agentStep', handler)
      stopStream()
    }
  }, [stopStream])

  // =====================
  // SEND MESSAGE
  // =====================
  const sendMessage = useCallback(
    async (content: string) => {
      console.log('[useChat] sendMessage called:', content)
      if (isSendingRef.current || !content.trim()) return

      // reset previous safety timeout
      if (safetyTimeoutRef.current) {
        clearTimeout(safetyTimeoutRef.current)
        safetyTimeoutRef.current = null
      }

      isSendingRef.current = true
      isStreamActiveRef.current = true
      isCompletedRef.current = false
      contentRef.current = ''

      const requestId = generateId()
      const assistantMessageId = generateId()

      currentRequestIdRef.current = requestId
      assistantMessageIdRef.current = assistantMessageId

      // Store for resume
      setCurrentMessage(requestId, content)

      // reset agent state
      reset()

      // messages
      addMessage({ role: 'user', content, id: generateId() })
      addMessage({
        role: 'assistant',
        content: '',
        status: 'thinking',
        id: assistantMessageId,
      })

      setLoading(true)

      const stepsData: AgentStep[] = [
        { id: 'step-analyzing', title: 'Analyzing request', status: 'pending' },
        { id: 'step-planning', title: 'Planning solution', status: 'pending' },
        { id: 'step-executing', title: 'Executing', status: 'pending' },
        { id: 'step-reviewing', title: 'Reviewing', status: 'pending' },
      ]

      start(stepsData)

      useChatStore
        .getState()
        .addLog(`🚀 Starting: ${content.slice(0, 30)}...`)

      const appendStream = (chunk: string) => {
        const prevLen = contentRef.current.length
        contentRef.current += chunk
        const totalLen = contentRef.current.length

        useChatStore.getState().setTokenCount(totalLen)

        // Log to DebugPanel when crossing 50-char boundaries
        const prev50 = Math.floor(prevLen / 50)
        const curr50 = Math.floor(totalLen / 50)
        if (curr50 > prev50 && totalLen > 0) {
          const preview = contentRef.current.slice(-50)
          useChatStore.getState().addLog(`[Token] "${preview}"`)
        }

        if (!rafRef.current) {
          rafRef.current = requestAnimationFrame(() => {
            rafRef.current = null
            if (isStreamActiveRef.current && !isCompletedRef.current) {
              updateMessageById(
                assistantMessageIdRef.current,
                () => contentRef.current,
                'streaming'
              )
            }
          })
        }
      }

      try {
        handlerCleanupRef.current = chatService.onMessage(
          (msg: Message) => {
            if (
              !isMountedRef.current ||
              !isStreamActiveRef.current ||
              isCompletedRef.current
            )
              return

            // FIX: Strict null check for message_id
            if (msg.message_id == null || msg.message_id === '') return
            if (msg.message_id !== currentRequestIdRef.current) return

            // DEBUG: Log all messages
            if (msg.type === 'done' || msg.status === 'done') {
              console.log('[useChat] Detected done message:', msg)
            }

            // ERROR
            if (msg.status === 'error') {
              isCompletedRef.current = true
              stopStream()

              updateMessageById(
                assistantMessageIdRef.current,
                () => msg.content,
                'error'
              )

              useChatStore
                .getState()
                .addLog(`❌ Error: ${msg.content}`)

              return
            }

            // STREAM CONTENT or STREAMING STATUS
            // Only append content - steps are managed by backend events
            if (msg.content || msg.status === 'streaming') {
              if (msg.content) {
                appendStream(msg.content)
              }
            }

            // DONE - also handle stream completion after inactivity
            // If we've been receiving content and then stop for 5+ seconds, assume done
            if (
              msg.done === true ||
              msg.status === 'done'
            ) {
              console.log('[useChat] Received done signal')
              if (isCompletedRef.current) return
              isCompletedRef.current = true

              stopStream()

              updateMessageById(
                assistantMessageIdRef.current,
                () => contentRef.current,
                'done'
              )

              useAgentStore
                .getState()
                .steps.forEach((s) => {
                  if (s.status !== 'done') updateStep(s.id, 'done')
                })

              saveToHistory()

              useChatStore
                .getState()
                .addLog(
                  `✅ Done (${contentRef.current.length} chars)`
                )
            }
          }
        )

        chatService.sendMessage(content, requestId)
      } catch (err) {
        stopStream()

        setError(
          err instanceof Error ? err.message : 'Error'
        )
      }

      // SAFETY TIMEOUT (5 minutes for slow models)
      safetyTimeoutRef.current = setTimeout(() => {
        if (isSendingRef.current && !isCompletedRef.current) {
          console.warn('[useChat] force cleanup timeout')

          isCompletedRef.current = true
          stopStream()
        }
      }, 300000)  // 5 minutes instead of 60s
    },
    [addMessage, updateMessageById, setLoading, setError, start, reset, saveToHistory]
  )

  // =====================
  // CLEAR
  // =====================
  const clear = useCallback(() => {
    stopStream()
    clearMessages()
    reset()
    setError(null)
  }, [clearMessages, reset, setError, stopStream])

  // =====================
  // CANCEL
  // =====================
  const cancel = useCallback(() => {
    isCompletedRef.current = true
    currentRequestIdRef.current = ''
    chatService.cancel()
    stopStream()
  }, [stopStream])

  const currentStep = steps.find((s) => s.status === 'active')

  return {
    messages,
    isLoading,
    error,
    isActive,
    currentStep,
    steps,
    sendMessage,
    clear,
    cancel,
  }
}