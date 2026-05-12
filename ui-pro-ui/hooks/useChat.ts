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
    messages,
    addMessage,
    updateMessageById,
    updateLastChunkIndex,
    setCurrentMessage,
    resetCurrentMessage,
    trimMessageHistory,
    getPromptById,
    saveToHistory,
    removeMessage,
    setLoading,
    setError,
    isLoading,
    error,
  } = useChatStore()

  const { steps, start, updateStep, reset: resetAgent } = useAgentStore()

  // Refs for mutable state
  const isSendingRef = useRef(false)
  const isStreamActiveRef = useRef(false)
  const contentRef = useRef('')
  const assistantMessageIdRef = useRef('')
  const safetyTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // ===================== MODEL RESOLUTION =====================
  const getCurrentModelInfo = useCallback(() => {
    const modelInfo = availableModels.find(m => 
      m.name === selectedModel || m.id === selectedModel
    )

    const provider = modelInfo?.provider || 'ollama'
    // Fallback model based on provider format (LM Studio uses slash, Ollama uses colon)
    const fallbackModel = provider === 'lmstudio' ? 'qwen/qwen3.5-9b' : 'qwen3.6:latest'
    const model = modelInfo?.id || selectedModel || fallbackModel

    return { model, provider }
  }, [selectedModel, availableModels])

  // ===================== INITIAL STEPS =====================
  const initialSteps = useMemo(() => [
    { id: 'step-analyzing', title: 'Analyzing request', status: 'pending' as const },
    { id: 'step-planning', title: 'Planning solution', status: 'pending' as const },
    { id: 'step-executing', title: 'Executing', status: 'pending' as const },
    { id: 'step-reviewing', title: 'Reviewing', status: 'pending' as const },
  ], [])

  // ===================== CORE GENERATION =====================
  const initializeNewGeneration = useCallback(async (
    content: string, 
    messageId: string, 
    assistantId: string
  ) => {
    assistantMessageIdRef.current = assistantId
    contentRef.current = ''

    addMessage({
      role: 'assistant',
      content: '',
      status: 'thinking',
      id: assistantId,
    })

    setLoading(true)
    resetAgent()
    start(initialSteps)

    const { model, provider } = getCurrentModelInfo()

    return chatService.sendMessage(content, messageId, 0, model, provider)
  }, [addMessage, setLoading, resetAgent, start, getCurrentModelInfo, initialSteps])

  // ===================== SEND MESSAGE =====================
  const sendMessage = useCallback(async (content: string) => {
    if (isSendingRef.current || !content.trim()) return

    if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current)

    isSendingRef.current = true
    isStreamActiveRef.current = true

    const messageId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    setCurrentMessage(messageId, content)
    addMessage({ role: 'user', content, id: crypto.randomUUID() })

    try {
      await initializeNewGeneration(content, messageId, assistantId)

      // Safety timeout
      safetyTimeoutRef.current = setTimeout(() => {
        if (isStreamActiveRef.current) {
          setError('Request timed out after 5 minutes')
          cancel()
        }
      }, 300_000)

    } catch (err) {
      console.error('[useChat] Send failed:', err)
      setError(err instanceof Error ? err.message : 'Failed to send message')
      isSendingRef.current = false
      isStreamActiveRef.current = false
    }
  }, [initializeNewGeneration, setCurrentMessage, addMessage, setError])

  // ===================== REGENERATE =====================
  const regenerate = useCallback(async (messageId: string) => {
    const userIndex = messages.findIndex(m => m.id === messageId && m.role === 'user')
    if (userIndex === -1) return

    const userMsg = messages[userIndex]
    const content = userMsg.content

    // Remove subsequent assistant messages
    messages.slice(userIndex + 1).forEach(m => removeMessage(m.id))

    const newMessageId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    isSendingRef.current = true
    isStreamActiveRef.current = true

    try {
      await initializeNewGeneration(content, newMessageId, assistantId)
    } catch (err) {
      console.error('[useChat] Regenerate failed:', err)
      setError('Failed to regenerate response')
    }
  }, [messages, removeMessage, initializeNewGeneration, setError])

  // ===================== CANCEL =====================
  const cancel = useCallback(() => {
    chatService.cancel()
    isStreamActiveRef.current = false
    isSendingRef.current = false

    if (safetyTimeoutRef.current) {
      clearTimeout(safetyTimeoutRef.current)
      safetyTimeoutRef.current = null
    }
  }, [])

  // Refs for values used in message handler
  const stepsRef = useRef(steps)
  const lastChunkIndexRef = useRef(lastReceivedChunkIndex)
  
  useEffect(() => { stepsRef.current = steps }, [steps])
  useEffect(() => { lastChunkIndexRef.current = lastReceivedChunkIndex }, [lastReceivedChunkIndex])

  // ===================== MESSAGE LISTENER =====================
  useEffect(() => {
    const unsubscribe = chatService.onMessage((msg: any) => {
      if (!isStreamActiveRef.current) return

      // Step updates
      if (msg.type === 'step' && msg.step_id) {
        updateStep(msg.step_id, msg.status === 'done' ? 'done' : 'active')
        return
      }

      // Token streaming
      if (msg.type === 'token' && msg.content) {
        contentRef.current += msg.content
        const newIndex = (lastChunkIndexRef.current || 0) + 1
        updateLastChunkIndex(newIndex)

        updateMessageById(assistantMessageIdRef.current, prev => prev + msg.content, 'streaming')
      }

      // Completion
      if (msg.type === 'done' || msg.done === true) {
        isStreamActiveRef.current = false
        isSendingRef.current = false

        updateMessageById(assistantMessageIdRef.current, () => contentRef.current, 'done')
        saveToHistory()

        // Mark all steps done
        initialSteps.forEach(step => updateStep(step.id, 'done'))

        resetCurrentMessage()
        trimMessageHistory()
        contentRef.current = ''

        if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current)
      }

      // Error handling
      if (msg.type === 'error') {
        isStreamActiveRef.current = false
        isSendingRef.current = false
        setError(msg.message || 'Unknown error')
        updateMessageById(assistantMessageIdRef.current, () => msg.message || '', 'error')
      }
    })

    return unsubscribe
  }, [
    updateMessageById,
    updateLastChunkIndex,
    saveToHistory,
    setError,
    updateStep,
    resetCurrentMessage,
    trimMessageHistory,
    initialSteps,
  ])

  // Auto-resume logic (when WS reconnects during active stream)
  useEffect(() => {
    if (!currentMessageId || lastReceivedChunkIndex <= 0) return

    const originalPrompt = getPromptById(currentMessageId)
    if (originalPrompt) {
      console.log(`[useChat] Auto-resuming ${currentMessageId} from chunk ${lastReceivedChunkIndex}`)
      const { model, provider } = getCurrentModelInfo()
      chatService.sendMessage(originalPrompt, currentMessageId, lastReceivedChunkIndex, model, provider)
    }
  }, [currentMessageId, lastReceivedChunkIndex, getPromptById, getCurrentModelInfo])

  return {
    messages,
    isLoading,
    error,
    steps,
    sendMessage,
    cancel,
    regenerate,
    stopGeneration: cancel,
    clear: () => {
      cancel()
      resetCurrentMessage()
      trimMessageHistory()
    },
  }
}