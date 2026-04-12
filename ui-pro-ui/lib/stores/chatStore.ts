// Chat Store - Zustand with event integration and history
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Message, ChatState, ChatHistoryItem } from '@/lib/types'
import { events } from '@/lib/events'

interface ChatStore extends ChatState {
  // History
  history: ChatHistoryItem[]
  currentChatId: string | null
  saveToHistory: (title?: string) => void
  loadChat: (id: string) => void
  deleteChat: (id: string) => void
  // Messages
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

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      messages: [],
      isLoading: false,
      error: null,
      history: [],
      currentChatId: null,

      // Generate title from first message
      _generateTitle: (messages: Message[]): string => {
        const firstUserMsg = messages.find(m => m.role === 'user')
        if (!firstUserMsg) return 'New Chat'
        const content = firstUserMsg.content.slice(0, 30)
        return content + (firstUserMsg.content.length > 30 ? '...' : '')
      },

      saveToHistory: (title?: string) => {
        const { messages, currentChatId, history } = get()
        if (messages.length === 0) return

        const now = new Date().toISOString()
        const chatTitle = title || get()._generateTitle(messages)

        if (currentChatId) {
          // Update existing
          set({
            history: history.map(chat =>
              chat.id === currentChatId
                ? { ...chat, messages, updatedAt: now }
                : chat
            ),
          })
        } else {
          // Create new
          const newChat: ChatHistoryItem = {
            id: `chat-${Date.now()}`,
            title: chatTitle,
            messages,
            createdAt: now,
            updatedAt: now,
          }
          set({
            history: [newChat, ...history],
            currentChatId: newChat.id,
          })
        }
      },

      loadChat: (id: string) => {
        const chat = get().history.find(c => c.id === id)
        if (chat) {
          set({
            messages: chat.messages,
            currentChatId: id,
          })
        }
      },

      deleteChat: (id: string) => {
        const { history, currentChatId } = get()
        set({
          history: history.filter(c => c.id !== id),
          currentChatId: currentChatId === id ? null : currentChatId,
        })
      },

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

      clearMessages: () => set({ messages: [], error: null, currentChatId: null }),

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error }),
    }),
    {
      name: 'ui-pro-chat',
      partialize: (state) => ({ history: state.history }),
    }
  )
)
