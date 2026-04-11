// Chat Store - Zustand with event integration
import { create } from 'zustand'
import type { Message, ChatState } from '@/lib/types'
import { events } from '@/lib/events'

interface ChatStore extends ChatState {
  addMessage: (message: Message) => void
  updateLastMessage: (content: string, status?: Message['status']) => void
  clearMessages: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

// Initialize event listeners
events.on('message', (data) => {
  const store = useChatStore.getState()
  if (data.role === 'assistant') {
    store.addMessage({
      id: `msg-${Date.now()}`,
      role: data.role,
      content: data.content,
      status: 'streaming',
    })
  }
})

events.on('status', (data) => {
  useChatStore.getState().setLoading(data.status === 'streaming')
})

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isLoading: false,
  error: null,

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateLastMessage: (content, status) =>
    set((state) => {
      const msgs = [...state.messages]
      const lastIdx = msgs.length - 1
      if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
        msgs[lastIdx] = { ...msgs[lastIdx], content, status: status || msgs[lastIdx].status }
      }
      return { messages: msgs }
    }),

  clearMessages: () => set({ messages: [], error: null }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),
}))
