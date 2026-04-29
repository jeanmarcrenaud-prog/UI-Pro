// chatController.ts
// Role: Feature-level chat controller - orchestrates the chat flow by managing user/assistant message
// creation, initial agent steps setup, stream service connection, and event-based token/step updates

// Chat Controller - Orchestrates chat flow with events
import { useChatStore } from '@/stores/chatStore'
import { useAgentStore } from '@/stores/agentStore'
import { streamService } from '@/services/streamService'

function generateId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export function useChatController() {
  const { 
    messages, 
    addMessage, 
    updateLastMessage, 
    clearMessages,
    isLoading 
  } = useChatStore()
  
  const { 
    setSteps, 
    updateStep,
    reset: resetAgent 
  } = useAgentStore()

  const sendMessage = async (content: string): Promise<void> => {
    if (!content.trim() || isLoading) return

    const userMessage = {
      id: generateId(),
      role: 'user' as const,
      content: content.trim(),
      timestamp: new Date().toISOString(),
    }

    const agentMessage = {
      id: generateId(),
      role: 'assistant' as const,
      content: '',
      status: 'streaming' as const,
      timestamp: new Date().toISOString(),
    }

    // Add user message
    addMessage(userMessage)
    
    // Add agent placeholder
    addMessage(agentMessage)
    
    // Set initial agent steps
    setSteps([
      { id: '1', title: 'Analyzing', status: 'active' },
      { id: '2', title: 'Planning', status: 'pending' },
      { id: '3', title: 'Executing', status: 'pending' },
      { id: '4', title: 'Reviewing', status: 'pending' },
    ])

    // Connect to stream
    await streamService.connect(content.trim())

    // Handle stream events locally
    const unsubscribe = streamService.onEvent((event) => {
      switch (event.type) {
        case 'token':
          // Append token to last message
          const state = useChatStore.getState()
          const msgs = state.messages
          const lastIdx = msgs.length - 1
          if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
            const currentContent = msgs[lastIdx].content
            useChatStore.setState({
              messages: [
                ...msgs.slice(0, lastIdx),
                { ...msgs[lastIdx], content: currentContent + event.data },
              ],
            })
          }
          break

        case 'step':
          if (event.stepId) {
            updateStep(event.stepId, event.data as 'active' | 'done')
          }
          break

        case 'tool':
          // Tool was called
          break

        case 'done':
          // Complete - mark final step done
          updateStep('4', 'done')
          unsubscribe()
          break

        case 'error':
          // Handle error
          break
      }
    })
  }

  const clear = (): void => {
    clearMessages()
    resetAgent()
  }

  return {
    messages,
    isLoading,
    sendMessage,
    clear,
  }
}