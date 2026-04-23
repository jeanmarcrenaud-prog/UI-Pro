import { motion } from 'framer-motion'
import { MarkdownRenderer } from '../markdown/MarkdownRenderer'
import { events } from '@/lib/events'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  status?: 'thinking' | 'streaming' | 'done' | 'error'
}

interface ChatMessageProps {
  msg: Message
}

export function ChatMessage({ msg }: ChatMessageProps) {
  const isAgent = msg.role === 'assistant' && msg.status === 'thinking'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''} overflow-hidden`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${
          msg.role === 'user'
            ? 'bg-violet-600'
            : msg.status === 'thinking'
            ? 'bg-purple-600'
            : msg.status === 'error'
            ? 'bg-red-600'
            : 'bg-emerald-600'
        }`}
      >
        {msg.role === 'user' ? '👤' : '🤖'}
      </div>

      {/* Message content */}
      <div
        className={`flex flex-col max-w-[70%] ${
          msg.role === 'user' ? 'items-end' : 'items-start'
        }`}
      >
        <ChatMessageContent msg={msg} />
      </div>
    </motion.div>
  )
}

interface ChatMessageContentProps {
  msg: Message
}

function ChatMessageContent({ msg }: ChatMessageContentProps) {
  if (msg.role === 'assistant' && msg.content && !msg.status) {
    return (
      <div className="text-slate-100">
        <MarkdownRenderer content={msg.content} />
      </div>
    )
  }

  // Also render MarkdownRenderer for 'done' status
  if (msg.role === 'assistant' && msg.content && msg.status === 'done') {
    return (
      <div className="text-slate-100">
        <MarkdownRenderer content={msg.content} />
      </div>
    )
  }

  // For all other assistant messages with content, use MarkdownRenderer
  // This ensures code is always in isolated scrollable containers
  if (msg.role === 'assistant' && msg.content) {
    return (
      <div className="text-slate-100">
        <MarkdownRenderer content={msg.content} />
      </div>
    )
  }

  if (msg.status === 'error') {
    return (
      <div className="text-red-400">
        <div>{msg.content}</div>
      </div>
    )
  }

  if (msg.role === 'user') {
    return <p className="text-white">{msg.content}</p>
  }

  return null
}

interface StreamingCursorProps {
  msg: Message
}

function StreamingCursor({ msg }: StreamingCursorProps) {
  if (msg.role !== 'assistant') return null

  // Only show cursor during streaming status
  if (msg.status === 'streaming') {
    return (
      <motion.span
        animate={{ opacity: [0, 1, 0] }}
        transition={{ repeat: Infinity, duration: 0.8 }}
        className="inline-block w-2 h-4 bg-emerald-400 ml-1"
      />
    )
  }

  return null
}