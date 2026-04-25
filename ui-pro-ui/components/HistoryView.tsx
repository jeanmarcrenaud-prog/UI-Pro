// HistoryView.tsx
// Role: History page - displays saved chat list with timestamps, previews, and delete functionality
// with confirm-on-second-click pattern and localStorage persistence via chatStore

'use client'

import { useState } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { motion } from 'framer-motion'

interface HistoryViewProps {
  onSelectChat?: (chatId: string) => void
  onClose?: () => void
}

export function HistoryView({ onSelectChat, onClose }: HistoryViewProps) {
  const { history, loadChat, deleteChat } = useChatStore()
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  // Sort by updatedAt
  const sortedHistory = [...history].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  )

  const handleSelect = (chatId: string) => {
    loadChat(chatId)
    onSelectChat?.(chatId)
  }

  const handleDelete = (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirmDelete === chatId) {
      deleteChat(chatId)
      setConfirmDelete(null)
    } else {
      setConfirmDelete(chatId)
    }
  }

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="p-4 border-b border-slate-800">
          <h2 className="text-xl font-semibold text-white">History</h2>
          <p className="text-sm text-slate-500">
            {history.length} chat{history.length !== 1 ? 's' : ''} saved
          </p>
        </div>

        {/* Chat List */}
        {sortedHistory.length === 0 ? (
          <div className="p-8 text-center">
            <div className="text-4xl mb-4">📜</div>
            <p className="text-slate-400">No chat history yet</p>
            <p className="text-sm text-slate-600 mt-2">
              Start a conversation and it will be saved automatically
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {sortedHistory.map((chat, index) => {
              const msgCount = chat.messages?.length ?? 0
              const previewMessage = chat.messages?.find(m => m.role === 'assistant')
              const preview = previewMessage?.content?.slice(0, 100) || '...'

              return (
                <motion.div
                  key={chat.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="p-4 hover:bg-slate-800/30 transition-colors cursor-pointer group min-h-[4rem]"
                  onClick={() => handleSelect(chat.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-white truncate">
                        {chat.title}
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        {msgCount} message{msgCount !== 1 ? 's' : ''} • {formatTime(chat.updatedAt)}
                      </p>
                      {msgCount > 0 && (
                        <p className="text-sm text-slate-500 mt-2 line-clamp-2">
                          {preview}
                        </p>
                      )}
                    </div>

                    {/* Delete button */}
                    <button
                      onClick={(e) => handleDelete(chat.id, e)}
                      className={`px-2 py-1 rounded text-xs transition-colors shrink-0 mt-1 ${
                        confirmDelete === chat.id
                          ? 'bg-red-600 text-white'
                          : 'text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100'
                      }`}
                    >
                      {confirmDelete === chat.id ? 'Confirm?' : '🗑️'}
                    </button>
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}