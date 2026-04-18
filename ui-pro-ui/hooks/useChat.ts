'use client'

import { useCallback, useEffect, useRef } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'
import type { Message, AgentStep } from '@/lib/types'

function generateId(): string {
  return crypto.randomUUID()
}

export function useChat() {
  const {
    messages,
    isLoading,
    error,
    addMessage,
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

  // Listen for step events from backend - keep ref fresh
  const updateStepRef = useRef(updateStep)
  updateStepRef.current = updateStep
  
  useEffect(() => {
    const handleStep = (data: { stepId: string; status: 'pending' | 'active' | 'done' }) => {
      useChatStore.getState().addLog(`🔄 Step: ${data.stepId} → ${data.status}`)
      updateStepRef.current(data.stepId, data.status)
    }
    events.on('agentStep', handleStep)
    return () => events.off('agentStep', handleStep)
  }, []) // Stable - one listener only

const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) return

    // Reset and start fresh
    reset()
    
    // User message
    addMessage({ role: 'user', content, id: generateId() })
    // Placeholder for assistant (will be replaced by streaming)
    addMessage({ role: 'assistant', content: '', status: 'thinking', id: generateId() })
    setLoading(true)

    const stepsData: AgentStep[] = [
      { id: 'step-analyzing', title: 'Analyzing request', status: 'active' },
      { id: 'step-planning', title: 'Planning solution', status: 'pending' },
      { id: 'step-executing', title: 'Executing', status: 'pending' },
      { id: 'step-reviewing', title: 'Reviewing', status: 'pending' },
    ]
    start(stepsData)
    useChatStore.getState().addLog(`🚀 Starting: ${content.substring(0, 30)}...`)

    let cleanup: (() => void) | null = null
    
    try {
      let tokenCount = 0
      const stepsRef = useRef({ ...steps }) // Capture current steps at start
      
      // Register handler and get cleanup
      cleanup = chatService.onMessage((msg) => {
        const currentSteps = [...stepsRef.current]
        
        if (msg.content && msg.content.length > 0) {
          tokenCount++
          
          // Advance step when first token arrives
          const currentActive = currentSteps.find(s => s.status === 'active')
          if (currentActive?.id === 'step-analyzing' && tokenCount === 1) {
            updateStep('step-analyzing', 'done')
            updateStep('step-planning', 'active')
          }
        }
        
        // Done - mark all steps complete
        if (msg.status === 'done') {
          if (cleanup) cleanup() // Clean handler when done
          currentSteps.forEach(s => updateStep(s.id, 'done'))
          useChatStore.getState().saveToHistory()
          useChatStore.getState().addLog(`✅ Done! ${tokenCount} tokens`)
          setLoading(false)
        }
      })

      chatService.sendMessage(content)
    } catch (err) {
      if (cleanup) cleanup() // Cleanup handler on error
      setError(err instanceof Error ? err.message : 'Error')
      setLoading(false)
    }
  }, [isLoading, addMessage, setLoading, setError, start, updateStep, reset]) // No steps dep

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
