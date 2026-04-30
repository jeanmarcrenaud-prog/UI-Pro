// ChatContainer.tsx
// Role: Main chat container with messages, step progress, and input

'use client'

import { useMemo, useState, useCallback } from 'react'
import type { Message, AgentStep } from '@/lib/types'
import { useChat } from '@/hooks/useChat'
import { ChatMessages } from './chat/ChatMessages'
import { ExamplesList } from './chat/ExamplesList'
import { LoadingIndicator } from './chat/LoadingIndicator'
import { StepProgress } from './chat/StepProgress'
import { motion } from 'framer-motion'
import { useI18n } from '@/lib/i18n'
import { useUIStore } from '@/lib/stores/uiStore'

interface ChatContainerProps {
  messages?: Message[]
  agentSteps?: AgentStep[]
  locale?: 'en' | 'fr'
}

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

export function ChatContainer({
  messages: propMessages = [],
  agentSteps: propAgentSteps = [],
}: ChatContainerProps) {
  const {
    messages: hookMessages,
    isLoading,
    sendMessage,
    steps,
  } = useChat()

  const { locale = 'fr' } = useUIStore()
  const { t, setLocale } = useI18n()

  const [inputValue, setInputValue] = useState('')

  // Source priority: props > hook
  const messages = propMessages.length > 0 ? propMessages : hookMessages
  const agentSteps = propAgentSteps.length > 0 ? propAgentSteps : steps

  // Step progress visibility
  const stepsMessage = useMemo(() => {
    if (!agentSteps?.length) return null
    return agentSteps
  }, [agentSteps])

  // =====================
  // HANDLERS
  // =====================
  const handleSend = useCallback(() => {
    const trimmed = inputValue.trim()
    if (!trimmed || isLoading) return

    sendMessage(trimmed)
    setInputValue('')
  }, [inputValue, isLoading, sendMessage])

  const handleExampleSelect = useCallback((prompt: string) => {
    sendMessage(prompt)
  }, [sendMessage])

  return (
    <div className="flex-1 flex flex-col">

      {/* ===================== */}
      {/* MESSAGES AREA */}
      {/* ===================== */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">

        {/* Empty state - show examples */}
        {messages.length === 0 ? (
          <ExamplesList
            examples={DEFAULT_EXAMPLES}
            onSelect={handleExampleSelect}
            disabled={isLoading}
          />
        ) : (
          <ChatMessages messages={messages} />
        )}

        {/* Agent step progress */}
        {stepsMessage && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <StepProgress steps={stepsMessage} locale={locale} />
          </motion.div>
        )}

        {/* Loading state (before streaming starts) */}
        {isLoading && !messages.some(m => m.status === 'streaming') && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <LoadingIndicator label={t.loading.dots} />
          </motion.div>
        )}

        {/* Streaming status */}
        {messages.some(m => m.status === 'streaming') && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3"
          >
            <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs">
              ✨
            </div>
            <div className="bg-slate-800 rounded-2xl px-4 py-2">
              <span className="text-sm text-slate-300 flex items-center gap-2">
                <motion.span
                  animate={{ rotate: 360 }}
                  transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                  className="text-xs"
                >
                  ⚡
                </motion.span>
                {t.streaming.generating}
              </span>
            </div>
          </motion.div>
        )}
      </div>

      {/* ===================== */}
      {/* INPUT AREA */}
      {/* ===================== */}
      <div className="sticky bottom-0 bg-slate-950/80 backdrop-blur border-t border-slate-800 p-4">
        <div className="max-w-3xl mx-auto flex gap-2">
          <div className="flex-1 bg-[#0f172a] rounded-xl p-2 border border-slate-700 focus-within:border-violet-500">
            <textarea
              value={inputValue}
              disabled={isLoading}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={t.input.placeholder}
              rows={1}
              className="w-full bg-transparent text-white outline-none px-3 resize-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
            />
            <button
              onClick={handleSend}
              disabled={isLoading}
              className="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white px-4 py-1.5 rounded-lg ml-1"
            >
              ➤
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}