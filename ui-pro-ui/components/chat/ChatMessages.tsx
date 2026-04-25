// ChatMessages.tsx
// Role: Renders the list of filtered messages in the chat area

import { MessageBubble } from './MessageBubble'
import type { Message } from '@/lib/types'

export function ChatMessages({ messages }: { messages: Message[] }) {
  // Filter out null/undefined messages
  const displayMessages = messages
    .filter(m => 
      m && (m.role === 'user' || m.role === 'assistant' || m.role === 'system')
    )
    .map(m => ({...m, role: m.role as 'user' | 'assistant' | 'system'}))

  if (displayMessages.length === 0) {
    return null
  }

  return (
    <div className="flex-1 overflow-y-auto space-y-4 p-4">
      {displayMessages.map((msg, i) => (
        <MessageBubble
          key={`${msg.id ?? `msg-${i}`}`}
          message={msg}
        />
      ))}
    </div>
  )
}
