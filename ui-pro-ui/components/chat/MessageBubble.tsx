'use client'

// MessageBubble - Displays a single chat message
import type { Message, MessageStatus } from '@/lib/types'

interface MessageBubbleProps {
  message: Message
}

const statusIcons: Record<MessageStatus, string> = {
  thinking: '🤔',
  streaming: '⏳',
  done: '✅',
  error: '❌',
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const icon = message.status ? statusIcons[message.status] : null

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100'
        }`}
      >
        {icon && (
          <span className="mr-2 inline-block animate-pulse">{icon}</span>
        )}
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        {message.timestamp && (
          <span className="text-xs opacity-50">
            {new Date(message.timestamp).toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  )
}