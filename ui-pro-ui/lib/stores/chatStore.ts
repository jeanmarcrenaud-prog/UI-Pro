// Chat Store - Zustand with event integration and history
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Message, ChatState, ChatHistoryItem } from '@/lib/types'
import { events } from '@/lib/events'

// Log event types (only what's actually used)
const LogEvents = {
  LOG: 'log',
  TOKENS: 'tokens',
} as const

interface ChatStore extends ChatState {
  // Logs
  logs: string[]
  addLog: (message: string) => void
  clearLogs: () => void
  // Tokens
  tokenCount: number
  setTokenCount: (count: number) => void
  // History
  history: ChatHistoryItem[]
  currentChatId: string | null
  saveToHistory: (title?: string) => void
  loadChat: (id: string) => void
  deleteChat: (id: string) => void
  // Messages
  addMessage: (message: Message) => void
  updateLastMessage: (content: string, status?: Message['status']) => void
  updateMessageById: (id: string, updater: (content: string) => string, status?: Message['status']) => void
  clearMessages: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  // Internal
  _generateTitle: (messages: Message[]) => string
}

// Lazy-initialize event listeners (prevent duplication on hot-reload)
let _initialized = false
function _initEventListeners() {
  if (_initialized) return
  _initialized = true

  events.on('status', (data) => {
    useChatStore.getState().setLoading(data.status === 'streaming')
  })

  events.on(LogEvents.LOG, (data: { message?: string }) => {
    if (data.message) {
      useChatStore.getState().addLog(data.message)
    }
  })

  events.on(LogEvents.TOKENS, (data: { tokenCount?: number }) => {
    if (data.tokenCount !== undefined) {
      useChatStore.getState().setTokenCount(data.tokenCount)
    }
  })
}

// Initialize on first use (call once)
_initEventListeners()

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      // Logs
      logs: [],
      addLog: (message) =>
        set((state) => ({
          logs: [...state.logs, message],
        })),
      clearLogs: () => set({ logs: [] }),
      
      // Tokens
      tokenCount: 0,
      setTokenCount: (tokenCount) => set({ tokenCount }),
      
      // Messages
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

      updateMessageById: (id, updater, status) =>
        set((state) => ({
          messages: state.messages.map(m =>
            m.id === id
              ? { ...m, content: typeof updater === 'function' ? updater(m.content) : updater, status: status || m.status }
              : m
          )
        })),

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
