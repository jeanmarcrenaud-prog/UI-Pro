'use client'

// UI-Pro Chat Container - Premium with streaming & markdown

import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'

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

interface Props {
  messages: Message[]
  setMessages: (msgs: Message[]) => void
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  agentSteps?: AgentStep[]
}

export function ChatContainer({ messages, setMessages, isLoading, setIsLoading, agentSteps = [] }: Props) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Close WebSocket on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return
    
    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    }
    
    setMessages(prev => [...prev, userMessage])
    const userInput = input
    setInput('')
    setIsLoading(true)
    
    // Add thinking placeholder
    const assistantMessage: Message = {
      id: `msg-${Date.now()}-assistant`,
      role: 'assistant',
      content: '',
      status: 'thinking',
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, assistantMessage])
    
    try {
      // Try WebSocket first for streaming
      const wsUrl = `ws://${window.location.hostname}:8000/ws`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        ws.send(JSON.stringify({ message: userInput }))
      }

      ws.onmessage = (event) => {
        const data = event.data
        
        if (data === '[DONE]') {
          setIsLoading(false)
          ws.close()
          return
        }
        
        // Update last message with streaming content
        setMessages(prev => {
          const msgs = [...prev]
          const lastIdx = msgs.length - 1
          if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
            msgs[lastIdx] = {
              ...msgs[lastIdx],
              content: msgs[lastIdx].content + data,
              status: 'streaming',
            }
          }
          return msgs
        })
      }

      ws.onerror = () => {
        // Fallback to REST
        fetchChatREST()
      }

      ws.onclose = () => {
        setIsLoading(false)
      }
    } catch {
      // Fallback to REST
      fetchChatREST()
    }

    async function fetchChatREST() {
      try {
        const response = await fetch('http://localhost:8000/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: userInput }),
        })
        
        const data = await response.json()
        
        setMessages(prev => {
          const msgs = [...prev]
          const lastIdx = msgs.length - 1
          if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
            msgs[lastIdx] = {
              ...msgs[lastIdx],
              content: data.result || data.error || 'No response',
              status: data.status === 'error' ? 'error' : 'done',
            }
          }
          return msgs
        })
      } catch (error) {
        console.error('Error:', error)
        setMessages(prev => {
          const msgs = [...prev]
          const lastIdx = msgs.length - 1
          if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
            msgs[lastIdx] = {
              ...msgs[lastIdx],
              content: 'Failed to connect to backend',
              status: 'error',
            }
          }
          return msgs
        })
      } finally {
        setIsLoading(false)
      }
    }
  }, [input, isLoading, setMessages, setIsLoading])

  return (
    <div className="flex-1 flex flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center text-slate-400 mt-8"
          >
            <div className="text-6xl mb-4">👋</div>
            <h2 className="text-xl font-semibold mb-2">Welcome to UI-Pro</h2>
            <p className="text-sm">Your AI Agent Orchestration System</p>
            <p className="text-xs mt-4 text-slate-500">Describe the task you want to automate...</p>
          </motion.div>
        )}
        
        <AnimatePresence mode="popLayout">
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              {/* Avatar */}
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 ${
                msg.role === 'user' 
                  ? 'bg-violet-600' 
                  : 'bg-emerald-600'
              }`}>
                {msg.role === 'user' ? '👤' : '🤖'}
              </div>
              
              {/* Message with markdown */}
              <div className={`flex flex-col max-w-[70%] ${
                msg.role === 'user' ? 'items-end' : 'items-start'
              }`}>
                <div className="text-xs text-slate-500 mb-1">
                  {msg.role === 'user' ? 'You' : 'UI-Pro'}
                </div>
                <div
                  className={`rounded-2xl px-4 py-3 ${
                    msg.role === 'user'
                      ? 'bg-violet-600 text-white rounded-br-md'
                      : 'bg-slate-800 text-slate-100 rounded-bl-md'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown
                        components={{
                          code({ node, className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || '')
                            const isInline = !match && !className
                            return !isInline && match ? (
                              <SyntaxHighlighter
                                theme={oneDark}
                                language={match[1]}
                                PreTag="div"
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            ) : (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            )
                          }
                        }}
                      >
                        {msg.content || '...'}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                  
                  {/* Streaming cursor */}
                  {msg.status === 'streaming' && (
                    <motion.span
                      animate={{ opacity: [1, 0] }}
                      transition={{ repeat: Infinity, duration: 0.5 }}
                      className="inline-block w-2 h-4 bg-emerald-400 ml-1"
                    />
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {/* Agent Steps Timeline */}
        {agentSteps.length > 0 && isLoading && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex gap-2 flex-wrap justify-center"
          >
            {agentSteps.map((step, index) => (
              <div
                key={step.id}
                className={`px-3 py-1 rounded-full text-xs flex items-center gap-1 ${
                  step.status === 'done'
                    ? 'bg-green-900/50 text-green-400'
                    : step.status === 'active'
                    ? 'bg-blue-900/50 text-blue-400'
                    : 'bg-slate-800 text-slate-500'
                }`}
              >
                <span>{step.status === 'done' ? '✓' : index + 1}</span>
                <span className={step.status === 'active' ? 'animate-pulse' : ''}>
                  {step.title}
                </span>
              </div>
            ))}
          </motion.div>
        )}
        
        {/* Loading dots */}
        {isLoading && !messages.find(m => m.status === 'streaming') && (
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
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input */}
      <div className="p-4 border-t border-slate-700">
        <motion.div 
          className="flex gap-2 max-w-3xl mx-auto"
          whileFocus={{ scale: 1.01 }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                sendMessage()
              }
            }}
            placeholder="Describe your task..."
            className="flex-1 bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-violet-500 resize-none min-h-[50px] max-h-[200px] transition-colors"
            rows={1}
            disabled={isLoading}
          />
          <motion.button
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl px-4 py-3 font-medium transition-colors"
          >
            {isLoading ? (
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1 }}
              >
                ⏳
              </motion.span>
            ) : '➤'}
          </motion.button>
        </motion.div>
      </div>
    </div>
  )
}