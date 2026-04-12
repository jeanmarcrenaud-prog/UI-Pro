import { ChatMessage } from './ChatMessage'

export function ChatMessages({ messages }: any) {
  return (
    <div className="flex-1 overflow-y-auto space-y-4 p-4">
      {messages.map((msg: any) => (
        <ChatMessage key={msg.id} msg={msg} />
      ))}
    </div>
  )
}