// components/MessageBubble.tsx
'use client'

import type { Message } from '@/lib/types'
import { MarkdownRenderer } from '@/components/markdown'
import { memo } from 'react'
import { motion } from 'framer-motion'

interface MessageBubbleProps {
  message: Message
}

const statusIcons: Record<string, string> = {
  thinking: '🤖',
  streaming: '⏳',
  done: '✅',
  error: '❌',
}

const containerVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { 
      duration: 0.35, 
      ease: 'easeOut' as const
    }
  },
}

const userVariants = {
  hidden: { opacity: 0, x: 30 },
  visible: { 
    opacity: 1, 
    x: 0,
    transition: { duration: 0.4, ease: 'easeOut' as const }
  },
}

const assistantVariants = {
  hidden: { opacity: 0, x: -30 },
  visible: { 
    opacity: 1, 
    x: 0,
    transition: { duration: 0.4, ease: 'easeOut' as const }
  },
}

export const MessageBubble = memo(function MessageBubble({ 
  message 
}: MessageBubbleProps) {
  if (!message?.role) return null

  const isUser = message.role === 'user'
  const statusIcon = message.status ? statusIcons[message.status] : null
  const isStreaming = message.status === 'streaming'

  return (
    <motion.div
      className={`flex gap-3 w-full ${isUser ? 'justify-end' : 'justify-start'}`}
      initial="hidden"
      animate="visible"
      variants={isUser ? userVariants : assistantVariants}
      layout
    >
      {/* Assistant Avatar */}
      {!isUser && (
        <motion.div 
          className="flex-shrink-0 w-9 h-9 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-lg shadow-sm"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          🤖
        </motion.div>
      )}

      {/* Message Bubble */}
      <motion.div
        className={`relative max-w-[82%] px-5 py-3.5 rounded-3xl break-words shadow-sm ${
          isUser
            ? 'bg-violet-600 text-white rounded-br-none'
            : 'bg-slate-800 text-slate-100 rounded-bl-none'
        }`}
        whileHover={{ scale: 1.01 }}
        transition={{ duration: 0.2 }}
      >
        {/* Status Icon */}
        {statusIcon && (
          <motion.span 
            className="mr-2 inline-block"
            animate={isStreaming ? { rotate: [0, 10, -10, 0] } : {}}
            transition={{ repeat: isStreaming ? Infinity : 0, duration: 1.2 }}
          >
            {statusIcon}
          </motion.span>
        )}

        {/* Content */}
        {isUser ? (
          <div className="whitespace-pre-wrap text-[15px] leading-relaxed">
            {message.content}
          </div>
        ) : (
          <div className="prose prose-invert prose-slate max-w-none text-[15px] leading-relaxed">
            <MarkdownRenderer content={message.content || ''} />
          </div>
        )}

        {/* Timestamp */}
        {message.timestamp && (
          <motion.div 
            className="mt-2.5 flex items-center gap-1.5 opacity-70"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.7 }}
            transition={{ delay: 0.6 }}
          >
            <div className="w-1 h-1 rounded-full bg-current" />
            <span className="text-xs font-light">
              {new Date(message.timestamp).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </motion.div>
        )}
      </motion.div>

      {/* User Avatar */}
      {isUser && (
        <motion.div 
          className="flex-shrink-0 w-9 h-9 rounded-2xl bg-violet-500 flex items-center justify-center text-white text-sm font-medium self-end"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.15 }}
        >
          You
        </motion.div>
      )}
    </motion.div>
  )
})