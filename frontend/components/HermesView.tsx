// HermesView.tsx
// Role: Hermes Intelligence tab - chat interface for the Hermes MCP server
'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { useI18n } from '@/lib/i18n'
import { API_CONFIG } from '@/lib/config'
import { motion } from 'framer-motion'


// ─── Types ──────────────────────────────────────

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface HermesStatus {
  available: boolean
  tools: { name: string; description: string }[]
}

// ─── API helpers ─────────────────────────────────

const API_BASE = `${(API_CONFIG.apiUrl || '').replace(/\/$/, '')}/api/hermes`

async function fetchStatus(): Promise<HermesStatus> {
  try {
    const res = await fetch(`${API_BASE}/status`)
    if (!res.ok) throw new Error(`Hermes API error (${res.status})`)
    return res.json()
  } catch (e: any) {
    throw new Error(e.message?.includes('fetch') ? 'Backend API not running. Start with: python run.py --api' : e.message)
  }
}

async function sendConversationStream(
  message: string,
  sessionId: string | null,
  onToken: (token: string) => void,
): Promise<string | null> {
  const res = await fetch(`${API_BASE}/conversation/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  const newSessionId = res.headers.get('X-Session-Id')
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail || 'Conversation failed')
  }
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No reader available')
  const decoder = new TextDecoder()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      // Parse SSE format: "data: {content}\n\n"
      for (const line of chunk.split('\n\n')) {
        const match = line.match(/^data:\s(.*)$/)
        if (match) {
          const token = match[1]
          // Detect SSE error events from server
          if (token.startsWith('[ERROR] ')) {
            throw new Error(token.replace('[ERROR] ', ''))
          }
          onToken(token)
      }
  }
  }
  } finally {
    reader.releaseLock()
  }
  return newSessionId
}

async function cancelConversation(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/conversation/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  }).catch(() => {})
}
// ─── Component ───────────────────────────────────

export function HermesView() {
  const { t } = useI18n()
  const [status, setStatus] = useState<HermesStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatConnecting, setChatConnecting] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)

  const chatEndRef = useRef<HTMLDivElement>(null)

  // Fetch status on mount
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchStatus()
      .then((s) => {
        if (!cancelled) setStatus(s)
      })
      .catch((e) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(async () => {
    const msg = input.trim()
    if (!msg || chatLoading) return

    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    setInput('')
    setChatLoading(true)
    setChatConnecting(true)

    // Add empty assistant message for streaming
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      const newSessionId = await sendConversationStream(msg, sessionId, (token) => {
        // Clear connecting state on first token
        setChatConnecting(false)
        setMessages((prev) => {
          const last = prev[prev.length - 1]
          if (last && last.role === 'assistant') {
            return [...prev.slice(0, -1), { ...last, content: last.content + token }]
          }
          return prev
        })
      })
      if (newSessionId) setSessionId(newSessionId)
    } catch (e: any) {
      // Replace the empty assistant message with the error
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: 'assistant', content: `Error: ${e.message}` },
      ])
    } finally {
      setChatLoading(false)
      setChatConnecting(false)
    }
  }, [input, chatLoading, chatConnecting, sessionId])

  const handleStop = useCallback(() => {
    if (sessionId) cancelConversation(sessionId)
    setChatLoading(false)
    setChatConnecting(false)
  }, [sessionId])

  const handleNewConversation = useCallback(() => {
    setMessages([])
    setSessionId(null)
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // ── Loading state ─────────────────────────────
  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex-1 p-8 flex items-center justify-center"
      >
        <div className="text-center">
          <div className="text-4xl mb-4 animate-bounce">🧠</div>
          <p className="text-[var(--text-muted)]">Connecting to Hermes...</p>
        </div>
      </motion.div>
    )
  }

  // ── Error state ───────────────────────────────
  if (error) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex-1 p-8 flex items-center justify-center"
      >
        <div className="max-w-md text-center">
          <div className="text-6xl mb-6">🧠</div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-3">
            Hermes unavailable
          </h2>
          <p className="text-[var(--text-muted)] mb-4">{error}</p>
          <button
            onClick={() => {
              setLoading(true)
              setError(null)
              fetchStatus()
                .then(setStatus)
                .catch((e) => setError(e.message))
                .finally(() => setLoading(false))
            }}
            className="mt-4 px-6 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white text-sm font-medium hover:from-violet-700 hover:to-fuchsia-700 transition-all"
          >
            Retry
          </button>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.23, 1, 0.32, 1] }}
      className="flex-1 p-6 sm:p-8 overflow-y-auto"
    >
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-3xl">🧠</span>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Hermes</h1>
            <p className="text-sm text-[var(--text-muted)]">
              Intelligence Engine — Plan, delegate, execute
            </p>
          </div>
        </div>

        {/* Tools badges */}
        {status && (
          <div className="flex flex-wrap gap-2 mt-4">
            {status.tools.map((tool) => (
              <span
                key={tool.name}
                className="inline-flex items-center gap-1.5 text-xs font-medium py-1 px-2.5 rounded-full border bg-[var(--surface-secondary)] text-[var(--text-muted)] border-[var(--border-subtle)]"
              >
                {tool.name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Chat panel */}
      <div className="glass-panel rounded-2xl overflow-hidden flex flex-col h-[600px] max-w-3xl mx-auto">
        <div className="px-5 py-4 border-b border-[var(--border-subtle)] flex items-center gap-2">
          <span>💬</span>
          <span className="font-semibold text-sm text-[var(--text-primary)]">
            Talk to Hermes
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center text-[var(--text-muted)]/60 text-sm py-12 italic">
              Send a message to Hermes to start...
            </div>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-br-md'
                    : 'bg-[var(--surface-secondary)] text-[var(--text-primary)] rounded-bl-md'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="flex justify-start">
              {chatConnecting && (
                <div className="bg-[var(--surface-secondary)] rounded-2xl rounded-bl-md px-4 py-2.5 text-sm text-[var(--text-muted)]">
                  Connecting to Hermes...
                </div>
              )}
              <div className="bg-[var(--surface-secondary)] rounded-2xl rounded-bl-md px-4 py-2.5 text-sm">
                <span className="inline-flex gap-1">
                  <span className="animate-bounce">.</span>
                  <span className="animate-bounce" style={{ animationDelay: '0.1s' }}>.</span>
                  <span className="animate-bounce" style={{ animationDelay: '0.2s' }}>.</span>
                </span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-[var(--border-subtle)]">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe your task to Hermes..."
              disabled={chatLoading}
              className="flex-1 px-4 py-2.5 rounded-xl bg-[var(--surface-secondary)] border border-[var(--border-subtle)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]/50 outline-none focus:ring-2 focus:ring-violet-500/30 transition-all"
            />
            {chatLoading ? (
              <button
                onClick={handleStop}
                className="px-5 py-2.5 rounded-xl bg-red-600/90 text-white text-sm font-medium hover:bg-red-700 transition-all shrink-0"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={() => handleSend()}
                disabled={!input.trim()}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white text-sm font-medium disabled:opacity-40 hover:from-violet-700 hover:to-fuchsia-700 transition-all shrink-0"
              >
                Send
              </button>
            )}
          </div>
          <div className="flex items-center justify-between mt-3">
            <button
              onClick={handleNewConversation}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            >
              + New conversation
            </button>
            {sessionId && (
              <span className="text-xs text-[var(--text-muted)]/60 font-mono">
                session: {sessionId}
              </span>
            )}
          </div>
      </div>
      </div>
    </motion.div>
  )
}
