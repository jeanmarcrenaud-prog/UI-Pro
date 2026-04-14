'use client'

import { useCallback } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { chatService } from '@/services/chatService'
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
    saveToHistory,
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

    // Reset previous steps before starting new conversation
    reset()

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
      { id: 'step-analyzing', title: 'Analyzing request', status: 'active' },
      { id: 'step-planning', title: 'Planning solution', status: 'pending' },
      { id: 'step-executing', title: 'Executing', status: 'pending' },
      { id: 'step-reviewing', title: 'Reviewing', status: 'pending' },
    ]

    start(stepsData)

    try {
      // Register message handler BEFORE sending - to catch streaming events
      chatService.onMessage((msg) => {
        // When we receive the first response chunk, move to Planning
        if (msg.status === 'streaming') {
          const currentActive = steps.find(s => s.status === 'active')
          if (currentActive?.id === 'step-analyzing') {
            updateStep('step-analyzing', 'done')
            updateStep('step-planning', 'active')
          } else if (currentActive?.id === 'step-planning') {
            updateStep('step-planning', 'done')
            updateStep('step-executing', 'active')
          }
        }
        // When response is done, move to Reviewing
        if (msg.status === 'done') {
          updateStep('step-executing', 'done')
          updateStep('step-reviewing', 'active')
          // After review, mark all done
          setTimeout(() => {
            steps.forEach((step) => updateStep(step.id, 'done'))
          }, 500)
          // Now loading is complete - save to history
          useChatStore.getState().saveToHistory()
        }
      })

      chatService.sendMessage(content)

      // Note: setLoading(false) and saveToHistory are called in the message handler
      // when the response is fully received (status === 'done')
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Unknown error'
      updateMessage(assistantMsg.id, errMsg, 'error')
      setError(errMsg)
      setLoading(false)
    }
  }, [isLoading, messages, addMessage, updateMessage, setLoading, setError, start, updateStep, reset, saveToHistory])

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
