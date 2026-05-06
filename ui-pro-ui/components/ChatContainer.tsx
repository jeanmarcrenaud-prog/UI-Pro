// components/chat/ChatContainer.tsx
'use client'

import { useState, useCallback, useMemo } from 'react'
import type { Message, AgentStep } from '@/lib/types'
import { useChat } from '@/hooks/useChat'
import { ChatMessages } from './chat/ChatMessages'
import { ChatSuggestions } from './chat/ChatSuggestions'
import { ExamplesList } from './chat/ExamplesList'
import { LoadingIndicator } from './chat/LoadingIndicator'
import { StepProgress } from './chat/StepProgress'
import { motion, AnimatePresence } from 'framer-motion'
import { useI18n } from '@/lib/i18n'

const DEFAULT_EXAMPLES = [
  {
    icon: '🐍',
    text: 'Create a Python script',
    prompt: 'Write a Python script that fetches weather data from Open-Meteo API and displays it with a nice formatted output',
  },
  {
    icon: '📊',
    text: 'Analyze code for bugs',
    prompt: 'Write a Python function to calculate fibonacci numbers and analyze it for performance issues and bugs',
  },
  {
    icon: '🔧',
    text: 'REST API with FastAPI',
    prompt: 'Write a FastAPI application with CRUD endpoints for a todo list, including models, routes, and error handling',
  },
  {
    icon: '🎨',
    text: 'React component',
    prompt: 'Write a React TypeScript component for a todo list with add, delete, and toggle completion features',
  },
  {
    icon: '🧪',
    text: 'Unit tests',
    prompt: 'Write pytest unit tests for a Python function that validates email addresses, including edge cases',
  },
  {
    icon: '🌐',
    text: 'JavaScript utility',
    prompt: 'Write a JavaScript utility function to debounce API calls with cancellation support',
  },
  {
    icon: '📦',
    text: 'Package structure',
    prompt: 'Write a Python package with __init__.py, main modules, and setup.py for distribution',
  },
  {
    icon: '🔒',
    text: 'Auth middleware',
    prompt: 'Write a FastAPI dependency for JWT authentication with token validation and error handling',
  },
]

interface ChatContainerProps {
  messages?: Message[]
  agentSteps?: AgentStep[]
}

export function ChatContainer({ 
  messages: propMessages = [], 
  agentSteps: propAgentSteps = [] 
}: ChatContainerProps) {
  const {
    messages: hookMessages,
    isLoading,
    sendMessage,
    stopGeneration,
    steps,
    regenerate,
  } = useChat()

  const { t, locale } = useI18n()

  const [inputValue, setInputValue] = useState('')

  // Priority: props > hook (useful for modal/preview modes)
  const messages = propMessages.length > 0 ? propMessages : hookMessages
  const agentSteps = propAgentSteps.length > 0 ? propAgentSteps : steps

  // Get last assistant message with code for suggestions
  const lastAssistantCode = useMemo(() => {
    const last = [...messages].reverse().find(m => m.role === 'assistant' && m.content?.includes('```'))
    return last?.content || undefined
  }, [messages])

  const isEmpty = messages.length === 0

  const handleSend = useCallback(() => {
    const trimmed = inputValue.trim()
    if (!trimmed || isLoading) return

    sendMessage(trimmed)
    setInputValue('')
  }, [inputValue, isLoading, sendMessage])

  const handleExampleSelect = useCallback((prompt: string) => {
    sendMessage(prompt)
  }, [sendMessage])

  const handleSuggestion = useCallback((messageId: string, prompt: string) => {
    // Prepend the suggestion prompt to the existing message content
    const message = messages.find(m => m.id === messageId)
    if (!message?.content) return
    
    // Prepend to input for review instead of sending immediately
    const enhancedPrompt = prompt + message.content
    setInputValue(enhancedPrompt)
  }, [messages])

  const handleStop = useCallback(() => {
    stopGeneration?.()
  }, [stopGeneration])

  // Auto-resize textarea
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const textarea = e.target
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`
    setInputValue(e.target.value)
  }

  const showStreamingIndicator = useMemo(() => {
    return messages.some(m => m.status === 'streaming')
  }, [messages])

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-700">
        <AnimatePresence mode="wait">
          {isEmpty ? (
            <ExamplesList
              examples={DEFAULT_EXAMPLES}
              onSelect={handleExampleSelect}
              disabled={isLoading}
            />
          ) : (
            <ChatMessages messages={messages} onSuggestion={handleSuggestion} onRegenerate={regenerate} />
          )}
        </AnimatePresence>

        {/* Step Progress */}
        <AnimatePresence>
          {agentSteps.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
            >
              <StepProgress steps={agentSteps} locale={locale} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Loading / Streaming Indicators */}
        <AnimatePresence>
          {isLoading && !showStreamingIndicator && (
            <LoadingIndicator label={t.loading?.dots || 'Thinking...'} />
          )}

          {showStreamingIndicator && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-3 pl-3"
            >
              <div className="w-7 h-7 rounded-full bg-emerald-600/20 flex items-center justify-center flex-shrink-0">
                <span className="text-emerald-400 text-lg">✦</span>
              </div>
              <div className="bg-slate-800 rounded-2xl px-5 py-2.5 text-sm text-slate-300 flex items-center gap-3">
                {t.streaming.generating}
                
                <button
                  onClick={handleStop}
                  className="ml-2 px-3 py-1 text-xs font-medium bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
                >
                  Stop
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Input Area */}
      <div className="sticky bottom-0 bg-gradient-to-t from-slate-950 via-slate-950 to-transparent pt-4 pb-6 px-4 border-t border-slate-800">
        <div className="max-w-4xl mx-auto">
          <div className="relative bg-slate-900 rounded-3xl border border-slate-700 focus-within:border-violet-500 transition-colors">
            <textarea
              value={inputValue}
              onChange={handleTextareaChange}
              disabled={isLoading}
              placeholder={t.input?.placeholder || 'Describe your task...'}
              rows={1}
              className="w-full bg-transparent text-white placeholder-slate-500 px-6 py-4 pr-20 resize-y min-h-[56px] max-h-[180px] outline-none text-[15px]"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
            />

            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoading}
              className="absolute bottom-4 right-4 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-700 disabled:text-slate-500 text-white p-3 rounded-2xl transition-all disabled:cursor-not-allowed"
              aria-label="Send message"
            >
              <span className="text-xl leading-none">↑</span>
            </button>
          </div>

          <p className="text-center text-[10px] text-slate-500 mt-3">
            UI-Pro can make mistakes. Consider checking important information.
          </p>

          {/* Contextual Suggestions */}
          <ChatSuggestions
            lastCode={lastAssistantCode}
            onSelect={(suggestion) => {
              setInputValue(suggestion)
            }}
          />
        </div>
      </div>
    </div>
  )
}