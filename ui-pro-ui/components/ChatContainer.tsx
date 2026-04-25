// ChatContainer.tsx
// Role: Main chat container - orchestrates messages display, agent steps, loading states and input area
// Renders welcome screen, message timeline, agent progress, streaming cursor, and sticky input

'use client'

import { useState } from 'react'
import type { Message, AgentStep } from '@/lib/types'
import { useChat } from '@/hooks/useChat'
import { ChatMessages } from './chat/ChatMessages'
import { AgentSteps } from './chat/AgentSteps'

// ToolCallDisplay unused - removing to avoid lint warnings
// import { ToolCallDisplay } from './chat/ToolCallDisplay'
import { motion } from 'framer-motion'

interface ChatContainerProps {
  messages?: Message[]
  agentSteps?: AgentStep[]
}

export function ChatContainer({
  messages: propMessages,
  agentSteps: propAgentSteps,
}: ChatContainerProps = {}) {
  const {
    messages: hookMessages,
    isLoading: hookIsLoading,
    sendMessage,
    currentStep,
    steps,
  } = useChat()

  // Controlled input state (avoids DOM-read anti-pattern)
  const [inputValue, setInputValue] = useState('')

  // Override hook values with props if provided (backward compatibility)
  const messages = propMessages || hookMessages
  const isLoading = hookIsLoading
  const agentSteps = propAgentSteps || steps
  // Wrap agentSteps in a message context
  const stepsMessage: { steps: AgentStep[] } | null = agentSteps?.length > 0 
    ? { steps: agentSteps } 
    : null

  const examples = [
    { icon: '🐍', text: 'Create a Python script for weather data', prompt: 'Create a Python script that fetches weather data from Open-Meteo API and displays it nicely' },
    { icon: '📊', text: 'Analyze my code for bugs', prompt: 'Analyze this code and identify any potential bugs or issues' },
    { icon: '🔧', text: 'Explain how async works in Python', prompt: 'Explain how async/await works in Python with examples' },
    { icon: '🌐', text: 'Help me write a REST API', prompt: 'Help me write a REST API with FastAPI for a todo list' },
    { icon: '🎨', text: 'Create a React component', prompt: 'Create a React component with state management and proper TypeScript typing' },
    { icon: '🧪', text: 'Write unit tests', prompt: 'Write comprehensive unit tests for this function with edge case coverage' },
  ]

  // Step progress indicator - find index of active step
  const activeIndex = steps.findIndex(s => s.status === 'active')
  const currentStepNumber = activeIndex >= 0 ? activeIndex + 1 : 1

  return (
    <div className="flex-1 flex flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 ? (
          /* Welcome screen */
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center text-slate-400 mt-8"
          >
            <div className="text-6xl mb-4">👋</div>
            <h2 className="text-xl font-semibold mb-2">Welcome to UI-Pro</h2>
            <p className="text-sm">Your AI Agent Orchestration System</p>

            {/* Example prompts - memoized for stable keys */}
            <div className="mt-8 max-w-md mx-auto">
              <p className="text-xs text-slate-500 mb-3">Try an example:</p>
              <div className="grid gap-2">
                {examples.map((example) => (
                  <button
                    key={example.prompt}
                    onClick={() => sendMessage(example.prompt)}
                    disabled={isLoading}
                    className="text-left p-3 bg-slate-900/50 hover:bg-slate-900 border border-slate-700 hover:border-violet-500 rounded-lg transition-colors text-sm"
                  >
                    <span className="mr-2">{example.icon}</span>
                    {example.text}
                  </button>
                ))}
              </div>
            </div>

            <p className="text-xs mt-8 text-slate-500">Or type your own request below...</p>
          </motion.div>
        ) : (
          /* Messages */
          <ChatMessages messages={messages} />
        )}

        {/* Agent Steps - INTEGRATED into assistant message */}
        {stepsMessage && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs">
              🤖
            </div>
            <div className="bg-slate-800 text-slate-200 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-2 whitespace-nowrap">
              {/* Show completion or active step number */}
              {stepsMessage.steps.every(s => s.status === 'done') ? (
                <span className="text-sm text-emerald-400">✅ Complete</span>
              ) : (
                <>
                  <span className="text-sm">{currentStepNumber}</span>
                  <span className="text-sm font-medium">⚙️ {stepsMessage.steps.find(s => s.status === 'active')?.title || 'Processing'}</span>
                </>
              )}
            </div>
          </motion.div>
        )}

        {/* Loading dots when no message is streaming */}
        {isLoading && !messages.find(m => m.status === 'streaming') && !messages.find(m => m.status === 'thinking') && stepsMessage === null && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3"
          >
            <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center">🤖</div>
            <div className="bg-slate-800 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-1">
              {[0, 150, 300].map((delay, i) => (
                <motion.span
                  key={`dot-${i}`}
                  animate={{ y: [0, -4, 0] }}
                  transition={{ repeat: Infinity, duration: 0.6, delay: delay / 1000 }}
                  className="w-2 h-2 bg-slate-400 rounded-full"
                />
              ))}
            </div>
          </motion.div>
        )}

      </div>

      {/* Input - STICKY + IMPROVED */}
      <div className="sticky bottom-0 w-full bg-slate-950/80 backdrop-blur border-t border-slate-800 p-4">
        <div className="max-w-3xl mx-auto flex gap-2">
          <div className="flex-1 bg-[#0f172a] rounded-xl p-2 border border-slate-700 focus-within:border-violet-500 transition-colors">
            <textarea
              placeholder="Describe your task..."
              disabled={isLoading}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="w-full bg-transparent outline-none text-white px-3 resize-none placeholder:text-slate-500"
              rows={1}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage(inputValue)
                  setInputValue('')
                }
              }}
            />
            <button
              onClick={() => {
                sendMessage(inputValue)
                setInputValue('')
              }}
              disabled={isLoading}
              className="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white px-4 py-1.5 rounded-lg ml-1 font-medium transition-colors flex items-center gap-2"
            >
              {isLoading && <motion.span animate={{ rotate: 360 }} transition={{ duration: 1 }} className="w-4 h-4 border border-white/20 border-t-white rounded-full" />}
              <span className={isLoading ? '' : 'font-medium'}>➤</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
