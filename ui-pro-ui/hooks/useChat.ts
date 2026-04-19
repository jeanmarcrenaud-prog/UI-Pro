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
    updateLastMessage,
    updateMessageById,
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

  // Refs for stable access inside callbacks (no stale closures)
  const updateStepRef = useRef(updateStep)
  updateStepRef.current = updateStep
  
  // Lock to prevent race condition on rapid sends
  const isSendingRef = useRef(false)
  
  // Track if we've already switched from thinking to streaming step
  const hasSwitchedStepRef = useRef(false)
  
  // Store references to avoid stale closures
  const stepsRef = useRef(steps)

  useEffect(() => {
    // Sync refs on each render
    stepsRef.current = steps
    
    // Register agentStep listener
    const handleStep = (data: { stepId: string; status: 'pending' | 'active' | 'done' }) => {
      useChatStore.getState().addLog(`🔄 Step: ${data.stepId} → ${data.status}`)
      updateStepRef.current(data.stepId, data.status)
    }
    
    events.on('agentStep', handleStep)
    
    return () => {
      events.off('agentStep', handleStep)
    }
  }, [steps])

  const sendMessage = useCallback(async (content: string) => {
    // Prevent race condition - double send
    if (isSendingRef.current) return
    if (!content.trim() || isLoading) return

    // Acquire lock
    isSendingRef.current = true
    hasSwitchedStepRef.current = false

    // Reset and start fresh
    reset()
    
    // User message  
    addMessage({ role: 'user', content, id: generateId() })
    
    // CRITICAL: Generate and store assistant ID at creation time (deterministic)
    const assistantId = generateId()
    addMessage({ role: 'assistant', content: '', status: 'thinking', id: assistantId })
    setLoading(true)

    const stepsData: AgentStep[] = [
      { id: 'step-analyzing', title: 'Analyzing request', status: 'active' },
      { id: 'step-planning', title: 'Planning solution', status: 'pending' },
      { id: 'step-executing', title: 'Executing', status: 'pending' },
      { id: 'step-reviewing', title: 'Reviewing', status: 'pending' },
    ]
    start(stepsData)
    useChatStore.getState().addLog(`🚀 Starting: ${content.substring(0, 30)}...`)

    let tokenCount = 0
    let handlerCleanup: (() => void) | null = null
    
    try {
      // Register handler and get cleanup from chatService
      handlerCleanup = chatService.onMessage((msg: Message) => {
        // Update tokens - use content length (more accurate than count++)
        if (msg.content && msg.content.length > 0) {
          tokenCount += msg.content.length
          // Sync tokenCount to store for DebugPanel
          useChatStore.getState().setTokenCount(tokenCount)
          
          // CRITICAL FIX: Use updateMessageById with deterministic assistantId
          // This is robust to reorder and multiple streams
          updateMessageById(
            assistantId,
            (prev: string) => prev + msg.content,
            'streaming'
          )
          
          // Advance step when first token arrives (only once)
          const currentSteps = stepsRef.current
          const currentActive = currentSteps.find(s => s.status === 'active')
          if (currentActive?.id === 'step-analyzing' && !hasSwitchedStepRef.current) {
            hasSwitchedStepRef.current = true
            updateStep('step-analyzing', 'done')
            updateStep('step-planning', 'active')
            
            // Get fresh steps and mark complete
            const completedSteps = useAgentStore.getState().steps
              .filter(s => s.status === 'done')
            if (completedSteps.length === currentSteps.length) {
              useChatStore.getState().saveToHistory()
              useChatStore.getState().addLog(`✅ Done! ${completedSteps.length} steps`)
            }
          }
        }
        
        // Done - check backend status field
        if (msg.done === true || msg.status === 'done') {
          handlerCleanup?.()
          // Mark all steps done
          stepsRef.current.forEach(s => updateStep(s.id, 'done'))
          useChatStore.getState().saveToHistory()
          useChatStore.getState().addLog(`✅ Done! ${tokenCount} chars`)
          setLoading(false)
          // Release lock
          isSendingRef.current = false
        }
      })

      // Send message
      chatService.sendMessage(content)
      
    } catch (err) {
      handlerCleanup?.()
      setError(err instanceof Error ? err.message : 'Error')
      setLoading(false)
      // Release lock on error
      isSendingRef.current = false
    }
  }, [isLoading, addMessage, updateLastMessage, updateMessageById, setLoading, setError, start, updateStep, reset])

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