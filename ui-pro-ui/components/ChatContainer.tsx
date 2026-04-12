'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism'


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

type AgentStatus = 'idle' | 'running' | 'error'

interface Props {
  messages: Message[]
  setMessages: (msgs: Message[]) => void
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  agentSteps?: AgentStep[]
  status?: AgentStatus
  onToggleDebug?: () => void
}

export function ChatContainer({ messages, setMessages, isLoading, setIsLoading, agentSteps = [] }: Props) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const hasStreamedRef = useRef(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  const sendMessage = useCallback(async (forcedInput?: string) => {
    const text = forcedInput ?? input
    if (!text.trim() || isLoading) return

    setInput('')
    hasStreamedRef.current = false
    setIsLoading(true)

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }

    const assistantMessage: Message = {
      id: `msg-${Date.now()}-assistant`,
      role: 'assistant',
      content: '',
      status: 'thinking',
      timestamp: new Date().toISOString(),
    }

    // ✅ insertion propre (1 seul setState)
    setMessages(prev => [...prev, userMessage, assistantMessage])

    const userInput = text

    try {
      const wsUrl = `ws://${window.location.hostname}:8000/ws`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        ws.send(JSON.stringify({ message: userInput }))
      }

      ws.onmessage = (event) => {
        const raw = event.data
        hasStreamedRef.current = true
        if (!raw) return

        if (raw === '[DONE]') {
          setIsLoading(false)
          ws.close()
          return
        }

        let delta = ''

        try {
          const parsed = JSON.parse(raw)

          delta = parsed.delta || parsed.text || parsed.content || parsed.result || ''

          if (parsed.code) {
            delta = '```python\n' + JSON.stringify(parsed.code, null, 2) + '\n```'
          }

          if (parsed.type === 'token') {
            delta = parsed.data || ''
          }
        } catch {
          delta = raw
        }

        if (!delta) return

        setMessages(prev => {
          const msgs = [...prev]
          const lastIdx = msgs.length - 1

          if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
            msgs[lastIdx] = {
              ...msgs[lastIdx],
              content: (msgs[lastIdx].content || '') + delta,
              status: 'streaming',
            }
          }

          return msgs
        })
      }

      ws.onerror = (event) => {
        console.error('WebSocket error:', event)
        if (!hasStreamedRef.current) fetchChatREST()
      }

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event)
        setIsLoading(false)
        wsRef.current = null
      }
    } catch (error) {
      console.error('WebSocket connection error:', error)
      fetchChatREST()
    }

    async function fetchChatREST() {
      try {
        const response = await fetch('http://localhost:8000/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: userInput }),
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const data = await response.json()

        let content = ''
        if (data.result) {
          content = data.result
        } else if (data.error) {
          content = data.error
        } else if (data.text) {
          content = data.text
        } else if (data.code) {
          content = '```python\n' + JSON.stringify(data.code, null, 2) + '\n```'
        } else if (data.files) {
          content = 'Files: ' + JSON.stringify(data.files, null, 2)
        } else {
          content = 'No response'
        }

        setMessages(prev => {
          const msgs = [...prev]
          const lastIdx = msgs.length - 1
          if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
            msgs[lastIdx] = {
              ...msgs[lastIdx],
              content: content,
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
              content: `Failed to connect to backend: ${error instanceof Error ? error.message : String(error)}`,
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

            {/* Example prompts */}
            <div className="mt-8 max-w-md mx-auto">
              <p className="text-xs text-slate-500 mb-3">Try an example:</p>
              <div className="grid gap-2">
                {[
                  { icon: '🐍', text: 'Create a Python script to fetch weather data', prompt: 'Create a Python script that fetches weather data from Open-Meteo API and displays it nicely' },
                  { icon: '📊', text: 'Analyze my code for bugs', prompt: 'Analyze this code and identify any potential bugs or issues' },
                  { icon: '🔧', text: 'Explain how async works in Python', prompt: 'Explain how async/await works in Python with examples' },
                  { icon: '🌐', text: 'Help me write a REST API', prompt: 'Help me write a REST API with FastAPI for a todo list' },
                ].map((example, i) => (
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
                  className={`rounded-2xl px-4 py-3 max-h-[60vh] overflow-y-auto custom-scrollbar ${
                    msg.role === 'user'
                      ? 'bg-violet-600 text-white rounded-br-md'
                      : 'bg-slate-800 text-slate-100 rounded-bl-md'
                  }`}
                >
                  {msg.role === 'assistant' && msg.content ? (
                    <div className="prose prose-invert prose-sm max-w-none">
                      <ReactMarkdown
                        components={{
                          code({ node, className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || '');
                            const isInline = !match && !className;

                            if (!isInline && match) {
                              return (
                                <div className="my-3 rounded-lg overflow-hidden border border-slate-700">
                                  <SyntaxHighlighter
                                    theme={oneDark}
                                    language={match[1]}
                                    PreTag="div"
                                    customStyle={{
                                      backgroundColor: '#0f172a',
                                      padding: '1rem',
                                      borderRadius: '0.5rem',
                                      fontSize: '0.875rem',
                                      lineHeight: '1.5',
                                      margin: 0,
                                      overflowX: 'auto',
                                    }}
                                  >
                                    {String(children).replace(/\n$/, '')}
                                  </SyntaxHighlighter>
                                </div>
                              );
                            } else {
                              return (
                                <code className={`bg-slate-900/50 px-1.5 py-0.5 rounded text-sm ${className || ''}`} {...props}>
                                  {children}
                                </code>
                              );
                            }
                          },
                          h1({ node, ...props }) {
                            return <h1 className="text-xl font-bold text-white mt-4 mb-2" {...props} />;
                          },
                          h2({ node, ...props }) {
                            return <h2 className="text-lg font-bold text-white mt-3 mb-2" {...props} />;
                          },
                          h3({ node, ...props }) {
                            return <h3 className="text-base font-bold text-white mt-2 mb-2" {...props} />;
                          },
                          ul({ node, ...props }) {
                            return <ul className="list-disc list-inside my-2 pl-4" {...props} />;
                          },
                          ol({ node, ...props }) {
                            return <ol className="list-decimal list-inside my-2 pl-4" {...props} />;
                          },
                          p({ node, ...props }) {
                            return <p className="my-2" {...props} />;
                          },
                          inlineCode({ node, ...props }) {
                            return <code className="bg-slate-900/50 px-1.5 py-0.5 rounded text-sm" {...props} />;
                          },
                        }}
                      >
                        {msg.content}
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

        {/* Agent Steps Timeline - Detailed */}
        {agentSteps.length > 0 && isLoading && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-slate-900/80 border border-slate-700 rounded-xl p-4 max-w-lg mx-auto"
          >
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">🤖</span>
              <span className="text-sm font-medium text-white">Agent Working</span>
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 2 }}
                className="ml-auto text-xs"
              >
                ⚡
              </motion.span>
            </div>

            <div className="space-y-2">
              {agentSteps.map((step, index) => (
                <div
                  key={step.id}
                  className={`flex items-center gap-3 text-sm ${
                    step.status === 'done'
                      ? 'text-green-400'
                      : step.status === 'active'
                      ? 'text-blue-400'
                      : 'text-slate-500'
                  }`}
                >
                  {/* Step icon */}
                  <span className="w-6 text-center">
                    {step.status === 'done' ? '✅' : step.status === 'active' ? '⚙️' : '⏳'}
                  </span>

                  {/* Step name */}
                  <span className={step.status === 'active' ? 'animate-pulse' : ''}>
                    {step.title}
                  </span>

                  {/* Status indicator */}
                  {step.status === 'active' && (
                    <motion.span
                      initial={{ width: 0 }}
                      animate={{ width: 'auto' }}
                      className="ml-auto text-xs bg-blue-500/20 px-2 py-0.5 rounded-full"
                    >
                      running...
                    </motion.span>
                  )}
                </div>
              ))}
            </div>
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