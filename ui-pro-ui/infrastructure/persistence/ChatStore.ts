// infrastructure/persistence/ChatStore.ts
// Role: Chat state store via Zustand with persistence

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Message, ChatState, ChatHistoryItem, AgentStepStatus } from '@/domain/entities'
import { events } from '@/infrastructure/events/EventBus'

interface ChatStore extends ChatState {
  currentMessageId: string | null
  lastReceivedChunkIndex: number
  currentStreamId: string | null
  messageHistory: Record<string, string>
  setCurrentMessage: (id: string, prompt: string) => void
  updateLastChunkIndex: (index: number) => void
  setCurrentStreamId: (id: string | null) => void
  abortCurrentStream: () => void
  resumeFromIndex: (index: number) => void
  resetCurrentMessage: () => void
  trimMessageHistory: () => void
  getPromptById: (id: string) => string | undefined
  logs: string[]
  addLog: (message: string) => void
  clearLogs: () => void
  tokenCount: number
  setTokenCount: (count: number) => void
  history: ChatHistoryItem[]
  currentChatId: string | null
  saveToHistory: (title?: string) => void
  loadChat: (id: string) => void
  deleteChat: (id: string) => void
  renameChat: (id: string, title: string) => void
  archiveChat: (id: string) => void
  unarchiveChat: (id: string) => void
  togglePinChat: (id: string) => void
  addTagToChat: (id: string, tag: string) => void
  removeTagFromChat: (id: string, tag: string) => void
  addMessage: (message: Message) => void
  updateLastMessage: (content: string, status?: Message['status']) => void
  updateMessageById: (
    id: string,
    updater: (content: string) => string,
    status?: Message['status']
  ) => void
  removeMessage: (id: string) => void
  clearMessages: () => void
  startNewChat: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  _generateTitle: (messages: Message[]) => string
}

// Initialize event listeners
let _initialized = false
function _initEventListeners() {
  if (_initialized) return
  _initialized = true

  events.on('status', (data) => {
    useChatStore.getState().setLoading(data.status === 'streaming')
  })

  events.on('log', (data) => {
    if (data.message) {
      useChatStore.getState().addLog(data.message)
    }
  })

  events.on('tokens', (data) => {
    if (data.tokenCount !== undefined) {
      useChatStore.getState().setTokenCount(data.tokenCount)
    }
  })
}

_initEventListeners()

export const chatStore = {
  getState: () => useChatStore.getState(),
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      currentMessageId: null,
      lastReceivedChunkIndex: 0,
      currentStreamId: null,
      messageHistory: {},
      logs: [],
      tokenCount: 0,
      messages: [],
      isLoading: false,
      error: null,
      history: [],
      currentChatId: null,

      setCurrentMessage: (id, prompt) =>
        set((state) => ({
          currentMessageId: id,
          lastReceivedChunkIndex: 0,
          messageHistory: { ...state.messageHistory, [id]: prompt },
        })),

      updateLastChunkIndex: (index) =>
        set({ lastReceivedChunkIndex: index }),

      setCurrentStreamId: (id) =>
        set({ currentStreamId: id }),

      abortCurrentStream: () => {
        const streamId = get().currentStreamId
        if (streamId) {
          set({ currentStreamId: null })
        }
      },

      resumeFromIndex: (index) => {
        set({ lastReceivedChunkIndex: index })
      },

      resetCurrentMessage: () =>
        set({ currentMessageId: null, lastReceivedChunkIndex: 0 }),

      trimMessageHistory: () =>
        set((state) => {
          const entries = Object.entries(state.messageHistory).slice(-20)
          return { messageHistory: Object.fromEntries(entries) }
        }),

      getPromptById: (id) => get().messageHistory[id],

      addLog: (message) =>
        set((state) => ({
          logs: [...state.logs, message].slice(-100),
        })),

      clearLogs: () => set({ logs: [] }),

      setTokenCount: (tokenCount) => set({ tokenCount }),

      _generateTitle: (messages: Message[]): string => {
        const firstUserMsg = messages.find((m) => m.role === 'user')
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
          set({
            history: history.map((chat) =>
              chat.id === currentChatId ? { ...chat, messages, updatedAt: now } : chat
            ),
          })
        } else {
          const newChat: ChatHistoryItem = {
            id: `chat-${Date.now()}`,
            title: chatTitle,
            messages,
            createdAt: now,
            updatedAt: now,
          }
          const updatedHistory = [newChat, ...history].slice(0, 50)
          set({
            history: updatedHistory,
            currentChatId: newChat.id,
          })
        }
      },

      loadChat: (id: string) => {
        const chat = get().history.find((c) => c.id === id)
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
          history: history.filter((c) => c.id !== id),
          currentChatId: currentChatId === id ? null : currentChatId,
        })
      },

      renameChat: (id: string, title: string) => {
        const { history } = get()
        set({
          history: history.map((c) =>
            c.id === id ? { ...c, title, updatedAt: new Date().toISOString() } : c
          ),
        })
      },

      archiveChat: (id: string) => {
        const { history } = get()
        set({
          history: history.map((c) =>
            c.id === id ? { ...c, archived: true, updatedAt: new Date().toISOString() } : c
          ),
        })
      },

      unarchiveChat: (id: string) => {
        const { history } = get()
        set({
          history: history.map((c) =>
            c.id === id ? { ...c, archived: false, updatedAt: new Date().toISOString() } : c
          ),
        })
      },

      togglePinChat: (id: string) => {
        const { history } = get()
        set({
          history: history.map((c) =>
            c.id === id ? { ...c, isPinned: !c.isPinned, updatedAt: new Date().toISOString() } : c
          ),
        })
      },

      addTagToChat: (id: string, tag: string) => {
        const { history } = get()
        set({
          history: history.map((c) =>
            c.id === id
              ? { ...c, tags: [...(c.tags || []), tag], updatedAt: new Date().toISOString() }
              : c
          ),
        })
      },

      removeTagFromChat: (id: string, tag: string) => {
        const { history } = get()
        set({
          history: history.map((c) =>
            c.id === id
              ? { ...c, tags: (c.tags || []).filter((t) => t !== tag), updatedAt: new Date().toISOString() }
              : c
          ),
        })
      },

      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message].slice(-100),
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
          messages: state.messages.map((m) =>
            m.id === id
              ? {
                  ...m,
                  content: typeof updater === 'function' ? updater(m.content) : updater,
                  status: status || m.status,
                }
              : m
          ),
        })),

      clearMessages: () => set({ messages: [], error: null, currentChatId: null }),

      startNewChat: () => set({ messages: [], error: null, currentChatId: null }),

      removeMessage: (id) =>
        set((state) => ({
          messages: state.messages.filter((m) => m.id !== id),
        })),

      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
    }),
    {
      name: 'ui-pro-chat',
      partialize: (state) => ({ history: state.history }),
    }
  )
)
