// useChatActions.ts
// Role: Chat actions - sendMessage, regenerate, cancel

'use client'

import { useCallback, useRef } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { useUIStore } from '@/lib/stores/uiStore'
import { chatService } from '@/services/chatService'
import type { AgentStep } from '@/lib/types'

export const useChatActions = () => {
  const { selectedModel, availableModels } = useUIStore()
  const {
    addMessage,
    updateMessageById,
    updateLastChunkIndex,
    setCurrentMessage,
    resetCurrentMessage,
    trimMessageHistory,
    saveToHistory,
    removeMessage,
    setLoading,
    setError,
    getPromptById,
    messages,
  } = useChatStore()

  const { start, updateStep, reset: resetAgent } = useAgentStore()

  // Refs pour l'état mutable pendant le streaming
  const isSendingRef = useRef(false)
  const isStreamActiveRef = useRef(false)
  const contentRef = useRef('')
  const assistantMessageIdRef = useRef('')
  const safetyTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const getCurrentModelInfo = useCallback(() => {
    // Strip any provider prefix from persisted selectedModel for lookup
    // (handles migration from old prefixed ID format)
    const strippedSelected = selectedModel.replace(/^(ollama|lmstudio|lemonade|llamacpp)-/, '')

    const modelInfo = availableModels.find(m =>
      m.name === strippedSelected || m.id === strippedSelected || m.id === selectedModel
    )

    const provider = modelInfo?.provider || 'ollama'
    const fallbackModel = provider === 'lmstudio'
      ? 'qwen/qwen3.5-9b'
      : 'qwen3.6:latest'

    return {
      model: modelInfo?.id || strippedSelected || fallbackModel,
      provider,
    }
  }, [selectedModel, availableModels])

  const initialSteps: AgentStep[] = [
    { id: 'step-analyzing', title: 'Analyzing request', status: 'pending' },
    { id: 'step-planning', title: 'Planning solution', status: 'pending' },
    { id: 'step-executing', title: 'Executing', status: 'pending' },
    { id: 'step-reviewing', title: 'Reviewing', status: 'pending' },
  ]

  const initializeNewGeneration = useCallback(async (
    content: string,
    messageId: string,
    assistantId: string,
    model: string,
    provider: string
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

    // Use passed model/provider directly - no race condition
    return chatService.sendMessage(content, messageId, 0, model, provider)
  }, [addMessage, setLoading, resetAgent, start])

  const cancel = useCallback(() => {
    chatService.cancel()

    isStreamActiveRef.current = false
    isSendingRef.current = false

    if (safetyTimeoutRef.current) {
      clearTimeout(safetyTimeoutRef.current)
      safetyTimeoutRef.current = null
    }
  }, [])

  const sendMessage = useCallback(async (content: string) => {
    if (isSendingRef.current || !content?.trim()) return

    cancel() // Nettoyage préalable

    // Capturer le modèle IMMÉDIATEMENT pour éviter race condition
    const { model, provider } = getCurrentModelInfo()

    isSendingRef.current = true
    isStreamActiveRef.current = true

    const messageId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    setCurrentMessage(messageId, content)
    addMessage({ role: 'user', content, id: crypto.randomUUID() })

    try {
      await initializeNewGeneration(content, messageId, assistantId, model, provider)

      safetyTimeoutRef.current = setTimeout(() => {
        if (isStreamActiveRef.current) {
          setError('Request timed out after 5 minutes')
          cancel()
        }
      }, 300_000)
    } catch (err) {
      console.error('[useChatActions] Send failed:', err)
      setError(err instanceof Error ? err.message : 'Failed to send message')
      isSendingRef.current = false
      isStreamActiveRef.current = false
    }
  }, [getCurrentModelInfo, initializeNewGeneration, setCurrentMessage, addMessage, setError, cancel])

  const regenerate = useCallback(async (messageId: string) => {
    const userIndex = messages.findIndex(m => m.id === messageId && m.role === 'user')
    if (userIndex === -1) return

    const content = messages[userIndex].content

    // Capture model immediately to avoid race condition
    const { model, provider } = getCurrentModelInfo()

    // Supprimer les messages suivants
    messages.slice(userIndex + 1).forEach(m => removeMessage(m.id))

    const newMessageId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    isSendingRef.current = true
    isStreamActiveRef.current = true

    try {
      await initializeNewGeneration(content, newMessageId, assistantId, model, provider)
    } catch (err) {
      console.error('[useChatActions] Regenerate failed:', err)
      setError('Failed to regenerate response')
    }
  }, [messages, removeMessage, initializeNewGeneration, getCurrentModelInfo, setError])

  return {
    sendMessage,
    regenerate,
    cancel,
    refs: {
      isSendingRef,
      isStreamActiveRef,
      contentRef,
      assistantMessageIdRef,
      safetyTimeoutRef,
    },
    initialSteps,
  }
}