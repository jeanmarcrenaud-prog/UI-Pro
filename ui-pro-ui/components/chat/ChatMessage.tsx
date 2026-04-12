import { motion } from 'framer-motion'
import { MarkdownRenderer } from '../markdown/MarkdownRenderer'

export function ChatMessage({ msg }: any) {
  return (
    <motion.div className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
      <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center">
        {msg.role === 'user' ? '👤' : '🤖'}
      </div>

      <div className="max-w-[70%]">
        {msg.role === 'assistant' ? (
          <MarkdownRenderer content={msg.content} />
        ) : (
          <p>{msg.content}</p>
        )}
      </div>
    </motion.div>
  )
}