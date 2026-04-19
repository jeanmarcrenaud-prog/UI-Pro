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
  
  // Track if component is mounted (lifecycle)
  const isMountedRef = useRef(true)
  
  // Track if stream is active (business logic)
  const isStreamActiveRef = useRef(false)
  
  // Safety timeout ref
  const safetyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  
  // RAF for batching updates (60fps max)
  const rafRef = useRef<number | null>(null)
  
  // Store references to avoid stale closures
  const stepsRef = useRef(steps)
  stepsRef.current = steps  // Sync outside useEffect

  // Safe event listener ref - declare OUTSIDE useEffect (React rules)
  const handleStepRef = useRef<(data: { stepId: string; status: 'pending' | 'active' | 'done' }) => void>()

  // Safe event listener with ref (100% safe in StrictMode)
  useEffect(() => {
    handleStepRef.current = (data: { stepId: string; status: 'pending' | 'active' | 'done' }) => {
      useChatStore.getState().addLog(`🔄 Step: ${data.stepId} → ${data.status}`)
      updateStepRef.current(data.stepId, data.status)
    }
    
    const handler = (data: { stepId: string; status: 'pending' | 'active' | 'done' }) => {
      handleStepRef.current?.(data)
    }
    
    events.on('agentStep', handler)
    
    return () => {
      events.off('agentStep', handler)
      // Cleanup handler and timeout on unmount
      isMountedRef.current = false
      isStreamActiveRef.current = false
      handlerCleanupRef.current?.()
      handlerCleanupRef.current = null
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current)
    }
  }, []) // Empty deps - only run once

  const sendMessage = useCallback(async (content: string) => {
    // Single guard check
    if (isSendingRef.current || !content.trim()) return

    // Acquire lock and reset state
    isSendingRef.current = true
    hasSwitchedStepRef.current = false
    isStreamActiveRef.current = true
    isCompletedRef.current = false
    contentRef.current = ''  // Single source of truth
    
    // Generate message ID first for consistent filtering
    const messageId = generateId()
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

    try {
      handlerCleanupRef.current = chatService.onMessage((msg: Message) => {
        // Safety: ignore if not mounted or stream not active
        if (!isMountedRef.current || !isStreamActiveRef.current || isCompletedRef.current) return
        
        // Strict filter by message_id (no race condition possible)
        if (msg.message_id !== currentMessageIdRef.current) return
        
        // Handle error status
        if (msg.status === 'error') {
          isCompletedRef.current = true  // Prevent double done
          updateMessageById(assistantId, () => msg.content, 'error')
          handlerCleanupRef.current?.()
          handlerCleanupRef.current = null
          setLoading(false)
          isSendingRef.current = false
          useChatStore.getState().addLog(`❌ Error: ${msg.content}`)
          return
        }
        
        // Update content - accumulate in single source of truth
        if (msg.content && msg.content.length > 0) {
          // Single source of truth: just accumulate
          contentRef.current += msg.content
          // Sync tokenCount to store (use contentRef.length - no need for charCount)
          useChatStore.getState().setTokenCount(contentRef.current.length)
          
          // Update message - use RAF for batching (60fps max)
          if (!rafRef.current) {
            rafRef.current = requestAnimationFrame(() => {
              // Early return guard (ultra safe)
              if (isStreamActiveRef.current && !isCompletedRef.current) {
                updateMessageById(assistantId, () => contentRef.current, 'streaming')
              }
              rafRef.current = null
            })
          }
          
          // Advance step when first token arrives
          if (!hasSwitchedStepRef.current) {
            hasSwitchedStepRef.current = true
            updateStep('step-analyzing', 'done')
            updateStep('step-planning', 'active')
          }
        }
        
        // Done - single source, prevent double
        if ((msg.done === true || msg.status === 'done') && !isCompletedRef.current) {
          isCompletedRef.current = true
          isStreamActiveRef.current = false
          
          // Flush any pending RAF only
          if (rafRef.current) {
            cancelAnimationFrame(rafRef.current)
            rafRef.current = null
          }
          
          // UN SINGLE update final (no double render)
          updateMessageById(assistantId, () => contentRef.current, 'done')
          
          handlerCleanupRef.current?.()
          handlerCleanupRef.current = null
          
          // Mark all steps done properly
          const currentSteps = useAgentStore.getState().steps
          currentSteps.forEach(s => {
            if (s.status !== 'done') updateStep(s.id, 'done')
          })
          useChatStore.getState().saveToHistory()
          useChatStore.getState().addLog(`✅ Done! ${contentRef.current.length} chars`)
          setLoading(false)
          isSendingRef.current = false
        }
      })

      // Send message with messageId for consistent filtering
      chatService.sendMessage(content, messageId)
      
    } catch (err) {
      handlerCleanupRef.current?.()
      handlerCleanupRef.current = null
      setError(err instanceof Error ? err.message : 'Error')
      setLoading(false)
      isSendingRef.current = false
    }
    
    // Safety timeout - force unlock if something goes wrong (with cleanup)
    clearTimeout(safetyTimeoutRef.current || undefined)
    safetyTimeoutRef.current = setTimeout(() => {
      if (isSendingRef.current && !isCompletedRef.current) {
        console.warn('[useChat] Safety: force unlock stuck state')
        isSendingRef.current = false
        isStreamActiveRef.current = false
        isCompletedRef.current = true
        handlerCleanupRef.current?.()
        handlerCleanupRef.current = null
        setLoading(false)
      }
    }, 60000)
  }, [addMessage, updateMessageById, setLoading, setError, start, updateStep, reset])

  const clear = useCallback(() => {
    // Cleanup first
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current)
    // Deactivate first to prevent race with incoming messages
    isStreamActiveRef.current = false
    // Cleanup handler on clear
    handlerCleanupRef.current?.()
    handlerCleanupRef.current = null
    clearMessages()
    reset()
    setError(null)
  }, [clearMessages, reset, setError])
  
  // Expose cancel for external use
  const cancel = useCallback(() => {
    // Invalidate stream first to prevent race
    isCompletedRef.current = true
    isStreamActiveRef.current = false
    currentMessageIdRef.current = ''
    chatService.cancel()
    handlerCleanupRef.current?.()
    handlerCleanupRef.current = null
    if (safetyTimeoutRef.current) clearTimeout(safetyTimeoutRef.current)
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    isSendingRef.current = false
    setLoading(false)
  }, [setLoading])

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
    cancel,
  }
}