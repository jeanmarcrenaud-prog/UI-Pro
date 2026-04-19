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
  
  // Current message ID for filtering
  const currentMessageIdRef = useRef('')
  
  // Track if stream is completed
  const isCompletedRef = useRef(false)
  
  // Single source of truth for content
  const contentRef = useRef('')
  
  // GLOBAL CLEANUP: store handler cleanup for unmount/cancel
  const handlerCleanupRef = useRef<(() => void) | null>(null)
  
  // Track if component is mounted
  const isActiveRef = useRef(true)
  
  // Store references to avoid stale closures
  const stepsRef = useRef(steps)
  stepsRef.current = steps  // Sync outside useEffect

  // Single listener registration
  useEffect(() => {
    const handleStep = (data: { stepId: string; status: 'pending' | 'active' | 'done' }) => {
      useChatStore.getState().addLog(`🔄 Step: ${data.stepId} → ${data.status}`)
      updateStepRef.current(data.stepId, data.status)
    }
    
    events.on('agentStep', handleStep)
    
    return () => {
      events.off('agentStep', handleStep)
      // Cleanup handler on unmount
      isActiveRef.current = false
      handlerCleanupRef.current?.()
    }
  }, []) // Empty deps - only run once

  const sendMessage = useCallback(async (content: string) => {
    // Single guard check
    if (isSendingRef.current || !content.trim()) return

    // Acquire lock and reset state
    isSendingRef.current = true
    hasSwitchedStepRef.current = false
    isActiveRef.current = true
    isCompletedRef.current = false
    contentRef.current = ''  // Single source of truth
    
    // Store message ID for filtering
    currentMessageIdRef.current = messageId
    
    // Clear previous handler to prevent double updates
    handlerCleanupRef.current?.()

    // Reset and start fresh
    reset()
    
    // User message  
    addMessage({ role: 'user', content, id: generateId() })
    
    // Assistant placeholder with deterministic ID
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

    let charCount = 0
    
    try {
      handlerCleanupRef.current = chatService.onMessage((msg: Message) => {
        // Safety: ignore if unmounted
        if (!isActiveRef.current) return
        
        // Filter by message_id if available (robust check)
        if (msg.message_id && currentMessageIdRef.current && msg.message_id !== currentMessageIdRef.current) {
          return
        }
        
        // Handle error status
        if (msg.status === 'error') {
          updateMessageById(assistantId, () => msg.content, 'error')
          handlerCleanupRef.current?.()
          setLoading(false)
          isSendingRef.current = false
          useChatStore.getState().addLog(`❌ Error: ${msg.content}`)
          return
        }
        
        // Update chars
        if (msg.content && msg.content.length > 0) {
          charCount += msg.content.length
          // Single source of truth: just accumulate
          contentRef.current += msg.content
          // Sync tokenCount to store
          useChatStore.getState().setTokenCount(charCount)
          
          // Update message - always use function for stability
          updateMessageById(assistantId, () => contentRef.current, 'streaming')
          
          // Advance step when first token arrives
          const currentSteps = stepsRef.current
          const currentActive = currentSteps.find(s => s.status === 'active')
          if (currentActive?.id === 'step-analyzing' && !hasSwitchedStepRef.current) {
            hasSwitchedStepRef.current = true
            updateStep('step-analyzing', 'done')
            updateStep('step-planning', 'active')
          }
        }
        
        // Done - single source, prevent double
        if ((msg.done === true || msg.status === 'done') && !isCompletedRef.current) {
          isCompletedRef.current = true
          updateMessageById(assistantId, () => contentRef.current, 'done')
          handlerCleanupRef.current?.()
          // Mark all steps done
          stepsRef.current.forEach(s => updateStep(s.id, 'done'))
          useChatStore.getState().saveToHistory()
          useChatStore.getState().addLog(`✅ Done! ${charCount} chars`)
          setLoading(false)
          isSendingRef.current = false
        }
      })

      // Send message with messageId for consistent filtering
      chatService.sendMessage(content, messageId)
      
    } catch (err) {
      handlerCleanupRef.current?.()
      setError(err instanceof Error ? err.message : 'Error')
      setLoading(false)
      isSendingRef.current = false
    }
  }, [addMessage, updateMessageById, setLoading, setError, start, updateStep, reset])

  const clear = useCallback(() => {
    // Deactivate first to prevent race with incoming messages
    isActiveRef.current = false
    // Cleanup handler on clear
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