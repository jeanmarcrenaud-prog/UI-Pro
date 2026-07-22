// HermesView.tsx
// Role: Hermes Intelligence tab - chat interface for the Hermes MCP server
'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useI18n } from '@/lib/i18n'

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

const API_BASE = 'http://localhost:8000/api/hermes'

async function fetchStatus(): Promise<HermesStatus> {
  const res = await fetch(`${API_BASE}/status`)
  if (!res.ok) throw new Error('Failed to fetch Hermes status')
  return res.json()
}

async function sendConversation(message: string): Promise<string> {
  const res = await fetch(`${API_BASE}/conversation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail || 'Conversation failed')
  }
  const data = await res.json()
  return data.response
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

    try {
      const response = await sendConversation(msg)
      setMessages((prev) => [...prev, { role: 'assistant', content: response }])
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${e.message}` },
      ])
    } finally {
      setChatLoading(false)
    }
  }, [input, chatLoading])

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
            <button
              onClick={handleSend}
              disabled={chatLoading || !input.trim()}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white text-sm font-medium disabled:opacity-40 hover:from-violet-700 hover:to-fuchsia-700 transition-all shrink-0"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
