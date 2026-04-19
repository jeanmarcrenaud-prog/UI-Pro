'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'
import type { Message, AgentStep, UseChatReturn } from '@/lib/types'

function generateId(): string {
  return crypto.randomUUID()
}

type CleanupFn = (() => void) | null

export const useChat = (): UseChatReturn => {
  const {
    messages,
    isLoading,
    error,
    addMessage,
    updateLastMessage,
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
  
  // Store references to avoid stale closures
  const stepsRef = useRef(steps)
  const messagesRef = useRef(messages)
  
  useEffect(() => {
    // Sync refs on each render
    messagesRef.current = messages
    stepsRef.current = steps
    
    // Register agentStep listener
    const handleStep = (data: { stepId: string; status: 'pending' | 'active' | 'done' }) => {
      useChatStore.getState().addLog(`🔄 Step: ${data.stepId} → ${data.status}`)
      updateStepRef.current(data.stepId, data.status)
    }
    
    // events.on doesn't return a cleanup function - we'll manually unsubscribe in cleanup
    try {
      events.on('agentStep', handleStep)
    } catch (e) {
      // events.on might throw in some edge cases, handle gracefully
    }
    
    return () => {
      // events.off to remove the listener
      events.off('agentStep', handleStep)
    }
  }, [messages, steps]) // Depend on values being synced via refs

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

    let tokenCount = 0
    let placeholderId: string | null = null
    let handlerCleanup: (() => void) | null = null
    
    try {
      // Register handler and get cleanup from chatService
      handlerCleanup = chatService.onMessage((msg: Message) => {
        // Get FRESH steps from store via ref (not stale closure)
        const currentSteps = stepsRef.current
        
        // Update placeholder message with streaming content
        if (msg.content && msg.content.length > 0) {
          tokenCount++
          // CRITICAL FIX: Sync tokenCount to store for DebugPanel display
          useChatStore.getState().setTokenCount(tokenCount)
          
          // Get fresh messages from ref on each invocation
          placeholderId = placeholderId || (messagesRef.current[messagesRef.current.length]?.id || generateId())
          
          // Use updateLastMessage to avoid duplicating messages
          if (placeholderId) {
            updateLastMessage(
              (useChatStore.getState().messages.find(m => m.id === placeholderId)?.content || '') + msg.content,
              'streaming'
            )
          }
          
          // Advance step when first token arrives
          const currentActive = currentSteps.find(s => s.status === 'active')
          if (currentActive?.id === 'step-analyzing' && tokenCount === 1) {
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
        
        // Done - check backend status field (done: true/false)
        if (msg.done === true || msg.status === 'done') {
          handlerCleanup?.()
          currentSteps.forEach(s => updateStep(s.id, 'done'))
          useChatStore.getState().saveToHistory()
          useChatStore.getState().addLog(`✅ Done! ${tokenCount} tokens`)
          setLoading(false)
        }
      })
      // No separate cleanup needed - handler manages its own lifecycle

      // Send message
      chatService.sendMessage(content)
      
    } catch (err) {
      handlerCleanup?.()
      setError(err instanceof Error ? err.message : 'Error')
      setLoading(false)
    }
  }, [isLoading, addMessage, updateLastMessage, setLoading, setError, start, updateStep, reset])

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
