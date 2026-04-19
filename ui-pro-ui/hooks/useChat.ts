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
  
  // GLOBAL CLEANUP: store handler cleanup for unmount/cancel
  const handlerCleanupRef = useRef<(() => void) | null>(null)
  
  // Store references to avoid stale closures
  const stepsRef = useRef(steps)
  stepsRef.current = steps  // Sync outside useEffect

  // Single listener registration (not dependent on steps)
  useEffect(() => {
    const handleStep = (data: { stepId: string; status: 'pending' | 'active' | 'done' }) => {
      useChatStore.getState().addLog(`🔄 Step: ${data.stepId} → ${data.status}`)
      updateStepRef.current(data.stepId, data.status)
    }
    
    events.on('agentStep', handleStep)
    
    return () => {
      events.off('agentStep', handleStep)
      // Also cleanup handler on unmount
      handlerCleanupRef.current?.()
    }
  }, []) // Empty deps - only run once

  const sendMessage = useCallback(async (content: string) => {
    // Prevent race condition - single guard is enough
    if (isSendingRef.current || !content.trim()) return

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

    // Accumulate content in ref for O(1) append (instead of O(n) string concat)
    const contentRef = { current: '' }
    let charCount = 0
    
    try {
      // Register handler and store cleanup for unmount
      handlerCleanupRef.current = chatService.onMessage((msg: Message) => {
        // Handle error status
        if (msg.status === 'error') {
          updateMessageById(assistantId, () => msg.content, 'error')
          handlerCleanupRef.current?.()
          setLoading(false)
          isSendingRef.current = false
          useChatStore.getState().addLog(`❌ Error: ${msg.content}`)
          return
        }
        
        // Update chars - use content length
        if (msg.content && msg.content.length > 0) {
          charCount += msg.content.length
          // Use ref for O(1) append (not O(n) string concat)
          contentRef.current += msg.content
          // Sync tokenCount to store for DebugPanel
          useChatStore.getState().setTokenCount(charCount)
          
          // CRITICAL FIX: Use updateMessageById with deterministic assistantId
          updateMessageById(
            assistantId,
            () => contentRef.current,
            'streaming'
          )
          
          // Advance step when first token arrives (only once)
          const currentSteps = stepsRef.current
          const currentActive = currentSteps.find(s => s.status === 'active')
          if (currentActive?.id === 'step-analyzing' && !hasSwitchedStepRef.current) {
            hasSwitchedStepRef.current = true
            updateStep('step-analyzing', 'done')
            updateStep('step-planning', 'active')
          }
        }
        
        // Done - check backend status field
        if (msg.done === true || msg.status === 'done') {
          handlerCleanupRef.current?.()
          // Mark all steps done
          stepsRef.current.forEach(s => updateStep(s.id, 'done'))
          useChatStore.getState().saveToHistory()
          useChatStore.getState().addLog(`✅ Done! ${charCount} chars`)
          setLoading(false)
          // Release lock
          isSendingRef.current = false
        }
      })

      // Send message
      chatService.sendMessage(content)
      
    } catch (err) {
      handlerCleanupRef.current?.()
      setError(err instanceof Error ? err.message : 'Error')
      setLoading(false)
      // Release lock on error
      isSendingRef.current = false
    }
  }, [addMessage, updateLastMessage, updateMessageById, setLoading, setError, start, updateStep, reset])

  const clear = useCallback(() => {
    // Cleanup on clear too
    handlerCleanupRef.current?.()
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