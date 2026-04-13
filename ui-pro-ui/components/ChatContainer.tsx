'use client'

import { useChat } from '@/hooks/useChat'
import { ChatMessages } from './chat/ChatMessages'
import { AgentSteps } from './chat/AgentSteps'
import { ToolCallDisplay } from './chat/ToolCallDisplay'
import { motion } from 'framer-motion'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  status?: 'thinking' | 'streaming' | 'done' | 'error'
}

interface AgentStep {
  id: string
  title: string
  detail?: string
  status: 'pending' | 'active' | 'done'
}

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

  // Override hook values with props if provided (backward compatibility)
  const messages = propMessages || hookMessages
  const isLoading = false // Use hook's isLoading
  const agentSteps = propAgentSteps || steps

  const examples = [
    { icon: '🐍', text: 'Create a Python script for weather data', prompt: 'Create a Python script that fetches weather data from Open-Meteo API and displays it nicely' },
    { icon: '📊', text: 'Analyze my code for bugs', prompt: 'Analyze this code and identify any potential bugs or issues' },
    { icon: '🔧', text: 'Explain how async works in Python', prompt: 'Explain how async/await works in Python with examples' },
    { icon: '🌐', text: 'Help me write a REST API', prompt: 'Help me write a REST API with FastAPI for a todo list' },
    { icon: '🎨', text: 'Create a React component', prompt: 'Create a React component with state management and proper TypeScript typing' },
    { icon: '🧪', text: 'Write unit tests', prompt: 'Write comprehensive unit tests for this function with edge case coverage' },
  ]

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

            {/* Example prompts */}
            <div className="mt-8 max-w-md mx-auto">
              <p className="text-xs text-slate-500 mb-3">Try an example:</p>
              <div className="grid gap-2">
                {examples.map((example, i) => (
                  <button
                    key={i}
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

        {/* Agent Steps */}
        {currentStep && (
          <AgentSteps steps={[{
            id: currentStep.id,
            title: currentStep.title,
            status: 'pending',
          }]} />
        )}

        {/* Loading dots */}
        {isLoading && !messages.find(m => m.status === 'streaming') && !messages.find(m => m.status === 'thinking') && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3"
          >
            <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center">🤖</div>
            <div className="bg-slate-800 rounded-2xl rounded-bl-md px-4 py-3 flex items-center gap-1">
              {[0, 150, 300].map((delay) => (
                <motion.span
                  key={delay}
                  animate={{ y: [0, -4, 0] }}
                  transition={{ repeat: Infinity, duration: 0.6, delay: delay / 1000 }}
                  className="w-2 h-2 bg-slate-400 rounded-full"
                />
              ))}
            </div>
          </motion.div>
        )}

      </div>

      {/* Input */}
      <div className="p-4 border-t border-slate-700">
        <motion.div
          className="flex gap-2 max-w-3xl mx-auto"
          whileFocus={{ scale: 1.01 }}
        >
          <div className="bg-[#0f172a] rounded-xl p-2">
            <textarea
              placeholder="Describe your task..."
              disabled={isLoading}
              className="w-full bg-transparent outline-none text-white px-3 resize-none"
              rows={1}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  const value = (e.target as HTMLTextAreaElement).value
                  sendMessage(value)
                  (e.target as HTMLTextAreaElement).value = ''
                }
              }}
            />
            <button
              onClick={() => {
                const value = (e.target as HTMLTextAreaElement).value
                sendMessage(value)
                (e.target as HTMLTextAreaElement).value = ''
              }}
              disabled={isLoading}
              className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-3 py-2 rounded-lg ml-1"
            >
              ➤
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
