// ChatMessages.tsx
// Role: Renders the list of filtered messages in the chat area

import { MessageBubble } from './MessageBubble'
import type { Message } from '@/lib/types'
import { useChatStore } from '@/lib/stores/chatStore'

interface ChatMessagesProps {
  messages: Message[]
  onRegenerate?: (messageId: string) => void
  onContinue?: (messageId: string) => void
  onSuggestion?: (messageId: string, prompt: string) => void
  onEdit?: (messageId: string) => void
}

export function ChatMessages({ messages, onRegenerate, onContinue, onSuggestion, onEdit }: ChatMessagesProps) {
  // Filter out null/undefined messages
  const displayMessages = messages
    .filter(m => 
      m && (m.role === 'user' || m.role === 'assistant' || m.role === 'system')
    )
    .map(m => ({...m, role: m.role as 'user' | 'assistant' | 'system'}))

  if (displayMessages.length === 0) {
    return null
  }

  // Get the last user message for regenerate action
  const lastUserMessage = [...displayMessages].reverse().find(m => m.role === 'user')

  return (
    <div className="flex-1 overflow-y-auto space-y-4 p-4">
      {displayMessages.map((msg, i) => (
        <MessageBubble
          key={`${msg.id ?? `msg-${i}`}`}
          message={msg}
          onRegenerate={msg.role === 'assistant' && msg.status === 'done' && lastUserMessage ? 
            () => onRegenerate?.(lastUserMessage.id) : undefined}
          onContinue={msg.role === 'assistant' && msg.status === 'done' ? 
            () => onContinue?.(msg.id) : undefined}
          onSuggestion={msg.role === 'assistant' && msg.status === 'done' ? 
            (prompt: string) => onSuggestion?.(msg.id, prompt) : undefined}
          onEdit={msg.role === 'user' ? () => onEdit?.(msg.id) : undefined}
        />
      ))}
    </div>
  )
}
