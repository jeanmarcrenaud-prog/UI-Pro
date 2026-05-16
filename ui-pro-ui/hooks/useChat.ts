// useChat.ts
// Role: Core React hook orchestrator - composes state, actions, and handlers

'use client'

import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { useChatActions } from './useChatActions'
import { useMessageHandler } from './useMessageHandler'

export const useChat = () => {
  const chatStore = useChatStore()
  const agentStore = useAgentStore()

  const {
    messages,
    isLoading,
    error,
    currentMessageId,
    lastReceivedChunkIndex,
    resetCurrentMessage,
    trimMessageHistory,
  } = chatStore

  const { steps } = agentStore

  const {
    sendMessage,
    regenerate,
    cancel,
    refs,
    initialSteps,
  } = useChatActions()

  // Gestion centralisée des messages et événements
  useMessageHandler({
    ...refs,
    updateMessageById: chatStore.updateMessageById,
    updateLastChunkIndex: chatStore.updateLastChunkIndex,
    updateStep: agentStore.updateStep,
    saveToHistory: chatStore.saveToHistory,
    resetCurrentMessage: chatStore.resetCurrentMessage,
    trimMessageHistory: chatStore.trimMessageHistory,
    setError: chatStore.setError,
    setTokenCount: chatStore.setTokenCount,
    setCurrentCode: chatStore.setCurrentCode,
    addLog: chatStore.addLog,
    initialSteps,
  })

  return {
    messages,
    steps,
    isLoading,
    error,
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