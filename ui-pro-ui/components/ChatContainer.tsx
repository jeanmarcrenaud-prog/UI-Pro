'use client'

// UI-Pro Chat Container - ChatGPT quality

import { useState, useRef, useEffect, useCallback } from 'react'

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

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'thinking': return '🧠'
      case 'streaming': return '⏳'
      case 'done': return '✅'
      case 'error': return '❌'
      default: return ''
    }
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="text-center text-slate-400 mt-8">
            <div className="text-6xl mb-4">👋</div>
            <h2 className="text-xl font-semibold mb-2">Welcome to UI-Pro</h2>
            <p className="text-sm">Your AI Agent Orchestration System</p>
            <p className="text-xs mt-4 text-slate-500">Describe the task you want to automate...</p>
          </div>
        )}
        
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            {/* Avatar */}
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
              msg.role === 'user' 
                ? 'bg-violet-600' 
                : 'bg-emerald-600'
            }`}>
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>
            
            {/* Message bubble */}
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
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.status && (
                  <span className="ml-2 text-xs">{getStatusIcon(msg.status)}</span>
                )}
                {msg.status === 'streaming' && (
                  <span className="animate-pulse ml-1">▍</span>
                )}
              </div>
            </div>
          </div>
        ))}
        
        {isLoading && !messages.find(m => m.status === 'streaming') && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center">🤖</div>
            <div className="bg-slate-800 rounded-2xl rounded-bl-md px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex gap-2 max-w-3xl mx-auto">
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
            className="flex-1 bg-slate-800 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-violet-500 resize-none min-h-[50px] max-h-[200px]"
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
            className="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl px-4 py-3 font-medium transition-colors"
          >
            {isLoading ? '⏳' : '➤'}
          </button>
        </div>
      </div>
    </div>
  )
}