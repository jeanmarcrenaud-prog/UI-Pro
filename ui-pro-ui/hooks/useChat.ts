'use client'

import { useCallback } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { apiService } from '@/services/api'
import type { Message, AgentStep } from '@/lib/types'

function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}

export function useChat() {
  const {
    messages,
    isLoading,
    error,
    addMessage,
    updateMessage,
    clearMessages,
    setLoading,
    setError,
  } = useChatStore()

  const {
    isActive,
    steps,
    start,
    updateStep,
    reset,
  } = useAgentStore()

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return

    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }

    const assistantMsg: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      status: 'thinking',
      timestamp: new Date().toISOString(),
    }

    addMessage(userMsg)
    addMessage(assistantMsg)

    setLoading(true)

    const stepsData: AgentStep[] = [
      { id: generateId(), title: 'Analyzing request', status: 'active' },
      { id: generateId(), title: 'Planning solution', status: 'pending' },
      { id: generateId(), title: 'Executing', status: 'pending' },
      { id: generateId(), title: 'Reviewing', status: 'pending' },
    ]

    start(stepsData)

    try {
      // Simulation progression
      setTimeout(() => {
        updateStep(stepsData[0].id, 'done')
        updateStep(stepsData[1].id, 'active')
      }, 300)

      const response = await apiService.chat(content)

      updateMessage(assistantMsg.id, response.result, 'done')

      stepsData.forEach(step => updateStep(step.id, 'done'))
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Unknown error'
      updateMessage(assistantMsg.id, errMsg, 'error')
      setError(errMsg)
    } finally {
      setLoading(false)

      // Delay pour UX propre
      setTimeout(() => reset(), 1200)
    }
  }, [isLoading, addMessage, updateMessage, setLoading, setError, start, updateStep, reset])

  const clear = useCallback(() => {
    clearMessages()
    reset()
    setError(null)
  }, [clearMessages, reset, setError])

  const currentStep = steps.find(s => s.status === 'active')

  return {
    messages,
    isLoading,
    error,
    isActive,
    currentStep,
    steps,
    sendMessage,
    clear,
  }
}