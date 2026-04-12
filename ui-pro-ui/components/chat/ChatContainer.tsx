'use client'

import { useChat } from '@/hooks/useChat'
import { ChatMessages } from './ChatMessages'
import { ChatInput } from './ChatInput'

export function ChatContainer() {
  const { messages, sendMessage, isLoading } = useChat()

  return (
    <div className="flex flex-col h-full">
      <ChatMessages messages={messages} />
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  )
}