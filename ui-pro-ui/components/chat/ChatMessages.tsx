import { MessageBubble } from './MessageBubble'
import type { Message } from '@/lib/types'

export function ChatMessages({ messages }: { messages: Message[] }) {
  // Filter out system and undefined messages
  const displayMessages = messages
    .filter(m => 
      m && (m.role === 'user' || m.role === 'assistant' || m.role === 'system')
    )
    .map(m => ({...m, role: m.role as 'user' | 'assistant' | 'system'}))

  return (
    <div className="flex-1 overflow-y-auto space-y-4 p-4">
      {displayMessages.map((msg, i) => (
        <MessageBubble key={msg.id || `msg-${i}`} role={msg.role as 'user' | 'assistant'} content={msg.content} />
      ))}
    </div>
  )
}
