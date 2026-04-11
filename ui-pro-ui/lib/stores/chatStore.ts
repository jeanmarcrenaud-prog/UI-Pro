// Chat Store - Zustand
import { create } from 'zustand'
import type { Message, ChatState } from '@/lib/types'

interface ChatStore extends ChatState {
  addMessage: (message: Message) => void
  updateMessage: (id: string, content: string, status?: Message['status']) => void
  clearMessages: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isLoading: false,
  error: null,

  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  updateMessage: (id, content, status) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content, status: status || m.status } : m
      ),
    })),

  clearMessages: () => set({ messages: [], error: null }),

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error }),
}))
