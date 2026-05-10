// useChat.ts
// Role: Core React hook for chat with WebSocket resume support

'use client'

import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { useUIStore } from '@/lib/stores/uiStore'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'
import type { Message } from '@/lib/types'

export const useChat = () => {
  const { selectedModel, availableModels } = useUIStore()
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
    removeMessage,
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
  const getCurrentModelInfo = useCallback(() => {
    // First try to find by name (display name), then by id
    let modelInfo = availableModels.find(m => m.name === selectedModel)
    if (!modelInfo) {
      modelInfo = availableModels.find(m => m.id === selectedModel)
    }
    
    const provider = modelInfo?.provider || 'ollama'
    // Fallback model based on provider format (LM Studio uses slash, Ollama uses colon)
    const fallbackModel = provider === 'lmstudio' ? 'qwen/qwen3.5-9b' : 'qwen3.6:latest'
    // Use model ID if found, otherwise use selectedModel as-is (could be id or display name)
    const model = modelInfo?.id || (selectedModel && (selectedModel.includes('/') || selectedModel.includes(':')) ? selectedModel : fallbackModel)
    console.log('[getCurrentModelInfo] selectedModel:', selectedModel, 'modelInfo:', modelInfo, '-> provider:', provider, 'model:', model)
    return {
      model,
      provider
    }
  }, [selectedModel, availableModels])

  // ===================== HELPER FUNCTIONS =====================
  // Initial steps - memoized to avoid recreation
  const initialSteps = useMemo(() => [
    { id: 'step-analyzing', title: 'Analyzing request', status: 'pending' as const },
    { id: 'step-planning', title: 'Planning solution', status: 'pending' as const },
    { id: 'step-executing', title: 'Executing', status: 'pending' as const },
    { id: 'step-reviewing', title: 'Reviewing', status: 'pending' as const },
  ], [])

  // Shared: initialize a new assistant message and start generation
  const initializeNewGeneration = useCallback((content: string, messageId: string, assistantId: string) => {
    // Reset state
    assistantMessageIdRef.current = assistantId
    contentRef.current = ''
    
    // Add messages
    addMessage({
      role: 'assistant',
      content: '',
      status: 'thinking',
      id: assistantId,
    })
    
    setLoading(true)
    resetAgent()
    start(initialSteps)
    
    // Get model info and start generation
    const { model, provider } = getCurrentModelInfo()
    return chatService.sendMessage(content, messageId, 0, model, provider)
  }, [addMessage, setLoading, resetAgent, start, getCurrentModelInfo])

  // ===================== REGENERATE =====================
  const handleRegenerate = useCallback(async (messageId: string) => {
    // Find the user message by ID
    const userMessageIndex = messages.findIndex(m => m.id === messageId && m.role === 'user')
    
    if (userMessageIndex === -1) {
      console.warn('[useChat] Cannot regenerate: user message not found')
      return
    }
    
    const userMsg = messages[userMessageIndex]
    const content = userMsg.content
    
    // Remove all messages after this user message (assistant responses)
    const messagesAfter = messages.slice(userMessageIndex + 1)
    messagesAfter.forEach(msg => removeMessage(msg.id))
    
    console.log('[useChat] Regenerating response for:', content.slice(0, 60) + '...')
    
    const newMessageId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()
    
    // Set sending flags
    isSendingRef.current = true
    isStreamActiveRef.current = true
    
    try {
      await initializeNewGeneration(content, newMessageId, assistantId)
    } catch (err) {
      console.error('[useChat] Regenerate failed:', err)
      setError('Failed to regenerate')
      isSendingRef.current = false
      isStreamActiveRef.current = false
    }
  }, [messages, removeMessage, initializeNewGeneration, setError])

  // Refs for values used in message handler (to avoid re-subscriptions)
  const stepsRef = useRef(steps)
  const lastChunkIndexRef = useRef(lastReceivedChunkIndex)
  
  // Keep refs in sync
  useEffect(() => { stepsRef.current = steps }, [steps])
  useEffect(() => { lastChunkIndexRef.current = lastReceivedChunkIndex }, [lastReceivedChunkIndex])

  const attemptResume = useCallback(async () => {
    if (!currentMessageId || lastReceivedChunkIndex <= 0) return

    const originalPrompt = getPromptById(currentMessageId)
    if (!originalPrompt) {
      console.warn('[useChat] Cannot resume: original prompt not found')
      return
    }

    console.log(`[useChat] Attempting resume → messageId: ${currentMessageId}, from chunk: ${lastReceivedChunkIndex}`)

    const { model, provider } = getCurrentModelInfo()
    try {
      await chatService.sendMessage(
        originalPrompt,
        currentMessageId,
        lastReceivedChunkIndex,
        model,
        provider
      )
    } catch (err) {
      console.error('[useChat] Resume failed:', err)
    }
  }, [currentMessageId, lastReceivedChunkIndex, getPromptById, getCurrentModelInfo])

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
        const newIndex = lastChunkIndexRef.current + 1
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

        // Force all steps to done (using ref)
        stepsRef.current.forEach((step) => {
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
    updateStep,
    resetCurrentMessage,
    trimMessageHistory,
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

    const messageId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    // Save for potential resume
    setCurrentMessage(messageId, content)

    // Add user message
    addMessage({ role: 'user', content, id: crypto.randomUUID() })

    try {
      // Use shared helper for assistant message + generation
      await initializeNewGeneration(content, messageId, assistantId)

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
    setCurrentMessage,
    initializeNewGeneration,
    setError,
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
    stopGeneration: cancel,  // Alias for backward compatibility
    clear,
    regenerate: handleRegenerate,
  }
}