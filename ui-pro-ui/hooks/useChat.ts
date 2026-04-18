'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
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
    
    // Cleanup on unmount - guaranteed cleanup
    let cleanup: (() => void) | null = null
    
    const handleStep = (data: { stepId: string; status: 'pending' | 'active' | 'done' }) => {
      useChatStore.getState().addLog(`🔄 Step: ${data.stepId} → ${data.status}`)
      updateStepRef.current(data.stepId, data.status)
    }
    events.on('agentStep', handleStep)
    
    return () => {
      events.off('agentStep', handleStep)
      if (cleanup) cleanup() // Cleanup handler on unmount
    }
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

    let tokenCount = 0
    let placeholderId: string | null = null
    let cleanup: (() => void) | null = null
    
    try {
      // Register handler and get cleanup from chatService
      cleanup = chatService.onMessage((msg: Message) => {
        // Get FRESH steps from store via ref (not stale closure)
        const currentSteps = stepsRef.current
        
        // Update placeholder message with streaming content
        if (msg.content && msg.content.length > 0) {
          tokenCount++
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
          if (cleanup) cleanup()
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
      if (cleanup) cleanup()
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
