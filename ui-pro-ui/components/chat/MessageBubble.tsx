'use client'

import type { Message } from '@/lib/types'

interface MessageBubbleProps {
  message: Message
}

// Status icons using our icon set
const statusIcons: Record<string, string> = {
  thinking: '🤖',
  streaming: '⏳',
  done: '✅',
  error: '❌',
}

export function MessageBubble({ message }: MessageBubbleProps) {
  // Guard against undefined/null messages
  if (!message || !message.role) return null

  const isUser = message.role === 'user'
  const icon = message.status ? statusIcons[message.status] : null

  return (
    <div className={`flex gap-3 w-full ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs">
          🤖
        </div>
      )}

      <div
        className={`relative max-w-[85%] px-4 py-3 rounded-2xl break-words ${
          isUser
            ? 'bg-violet-600 text-white rounded-br-md'
            : 'bg-slate-800 text-slate-200 rounded-bl-md'
        }`}
      >
        {/* Status icon */}
        {icon && (
          <span className="mr-2 inline-block animate-pulse">{icon}</span>
        )}

        {/* Message content */}
        <div className="whitespace-pre-wrap break-words">
          {message.content}
        </div>

        {/* Timestamp */}
        {message.timestamp && (
          <div className="flex items-center gap-1 mt-1">
            <span className="w-1 h-1 rounded-full bg-slate-500" />
            <span className="text-xs text-slate-500">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}