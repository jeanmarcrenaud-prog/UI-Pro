// useChat - Chat functionality hook
'use client'

import { useCallback, useRef } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { apiService } from '@/services/api'
import type { Message, AgentStep } from '@/lib/types'

function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}

export function useChat() {
  const { messages, isLoading, error, addMessage, updateMessage, clearMessages, setLoading, setError } = useChatStore()
  const { isActive, steps, start, updateStep, reset } = useAgentStore()
  const wsRef = useRef<WebSocket | null>(null)

  const sendMessage = useCallback(async (content: string) => {
    // Add user message
    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    }
    addMessage(userMsg)

    // Add thinking response
    const assistantMsg: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      status: 'thinking',
      timestamp: new Date().toISOString(),
    }
    addMessage(assistantMsg)

    setLoading(true)
    start([])

    try {
      // Initial agent steps
      const initialSteps: AgentStep[] = [
        { id: generateId(), title: 'Analyzing request', status: 'active' },
        { id: generateId(), title: 'Planning solution', status: 'pending' },
        { id: generateId(), title: 'Executing', status: 'pending' },
        { id: generateId(), title: 'Reviewing', status: 'pending' },
      ]
      start(initialSteps)

      const response = await apiService.chat(content)
      
      // Update message with response
      updateMessage(assistantMsg.id, response.result, 'done')
      
      // Mark all steps done
      initialSteps.forEach((step) => updateStep(step.id, 'done'))
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Unknown error'
      updateMessage(assistantMsg.id, errMsg, 'error')
      setError(errMsg)
    } finally {
      setLoading(false)
      reset()
    }
  }, [addMessage, updateMessage, setLoading, setError, start, updateStep, reset])

  const clear = useCallback(() => {
    clearMessages()
    clearSteps()
    setError(null)
  }, [clearMessages, clearSteps, setError])

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