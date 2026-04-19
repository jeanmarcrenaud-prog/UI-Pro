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
  
  // Current message ID for filtering multi-stream (must be useRef for persistence)
  const currentMessageIdRef = useRef('')
  
  // GLOBAL CLEANUP: store handler cleanup for unmount/cancel
  const handlerCleanupRef = useRef<(() => void) | null>(null)
  
  // Track if component is mounted to prevent updates after unmount
  const isActiveRef = useRef(true)
  
  // UI buffer for smooth streaming (must be useRef for persistence)
  const uiBufferRef = useRef('')
  const flushTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  
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
      // Mark inactive and cleanup handler on unmount
      isActiveRef.current = false
      handlerCleanupRef.current?.()
    }
  }, []) // Empty deps - only run once

  const sendMessage = useCallback(async (content: string) => {
    // Prevent race condition - single guard is enough
    if (isSendingRef.current || !content.trim()) return

    // Acquire lock
    if (isSendingRef.current) return
    isSendingRef.current = true
    hasSwitchedStepRef.current = false
    isActiveRef.current = true  // Reset active state after clear()
    // Store message ID for multi-stream filtering
    currentMessageIdRef.current = generateId()
    
    // Clear previous handler to prevent double updates
    handlerCleanupRef.current?.()

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
        // Safety: ignore if unmounted
        if (!isActiveRef.current) return
        
        // Future-proof: filter by message_id for multi-stream support
        if (msg.message_id && msg.message_id !== currentMessageIdRef.current) {
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
        
        // Update chars - use content length
        if (msg.content && msg.content.length > 0) {
          charCount += msg.content.length
          // Use ref for O(1) append (not O(n) string concat)
          contentRef.current += msg.content
          // Buffer UI updates for smooth rendering (avoid re-render on every chunk)
          uiBufferRef.current += msg.content
          // Sync tokenCount to store for DebugPanel
          useChatStore.getState().setTokenCount(charCount)
          
          // Flush buffer every 30ms for smooth UX
          clearTimeout(flushTimeoutRef.current || undefined)
          flushTimeoutRef.current = setTimeout(() => {
            if (uiBufferRef.current) {
              updateMessageById(assistantId, () => contentRef.current, 'streaming')
              uiBufferRef.current = ''
            }
          }, 30)
          
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
          // Flush remaining buffer
          clearTimeout(flushTimeoutRef.current || undefined)
          if (uiBufferRef.current) {
            updateMessageById(assistantId, () => contentRef.current, 'streaming')
            uiBufferRef.current = ''
          }
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
  }, [addMessage, updateMessageById, setLoading, setError, start, updateStep, reset])

  const clear = useCallback(() => {
    // Cleanup on clear (but don't deactivate - reset will handle it)
    clearTimeout(flushTimeoutRef.current || undefined)
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