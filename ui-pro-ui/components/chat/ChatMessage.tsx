import { motion } from 'framer-motion'
import { MarkdownRenderer } from '../markdown/MarkdownRenderer'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  status?: 'thinking' | 'streaming' | 'done'
}

interface ChatMessageProps {
  msg: Message
}

export function ChatMessage({ msg }: ChatMessageProps) {
  const isUser = msg.role === 'user'
  const isError = msg.status === 'error'
  const isThinking = msg.status === 'thinking'
  const isStreaming = msg.status === 'streaming'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
    >
      {/* AVATAR */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${
          isUser
            ? 'bg-violet-600'
            : isThinking
            ? 'bg-purple-600'
            : isError
            ? 'bg-red-600'
            : 'bg-emerald-600'
        }`}
      >
        {isUser ? '👤' : '🤖'}
      </div>

      {/* MESSAGE */}
      <div
        className={`flex flex-col max-w-[70%] ${
          isUser ? 'items-end' : 'items-start'
        }`}
      >
        {isThinking ? (
          <div className="text-sm text-slate-300">
            ⚡{msg.content || 'Generating...'}
          </div>
        ) : isError ? (
          <div className="text-red-400">
            {msg.content}
          </div>
        ) : isStreaming ? (
          <div className="text-slate-100">
            <MarkdownRenderer content={msg.content} />
            <motion.span
              animate={{ opacity: [0, 1, 0] }}
              transition={{ repeat: Infinity, duration: 0.8 }}
              className="inline-block w-2 h-4 bg-emerald-400 ml-1"
            />
          </div>
        ) : (
          <div className="text-slate-100">
            <MarkdownRenderer content={msg.content} />
          </div>
        )}
      </div>
    </motion.div>
  )
}
