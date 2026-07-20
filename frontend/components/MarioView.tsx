// MarioView.tsx
// Role: Mario Voice Assistant tab - TTS, STT, LLM conversation, and service status
// Integrates with backend /api/mario/* endpoints

'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { useI18n } from '@/lib/i18n'

// ─── Types ───────────────────────────────────────────

interface MarioStatus {
  available: boolean
  tts: boolean
  stt: boolean
  llm: boolean
  llm_service: string
  voices: string[]
  models: string[]
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// ─── API helpers ─────────────────────────────────────

const API_BASE = 'http://localhost:8000/api/mario'

async function fetchStatus(): Promise<MarioStatus> {
  const res = await fetch(`${API_BASE}/status`)
  if (!res.ok) throw new Error('Failed to fetch Mario status')
  return res.json()
}

async function sendConversation(message: string, temperature = 0.7): Promise<string> {
  const res = await fetch(`${API_BASE}/conversation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, temperature }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail || 'Conversation failed')
  }
  const data = await res.json()
  return data.response
}

async function speakText(text: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/tts/play`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  return res.ok
}

async function transcribeAudio(file: File): Promise<string> {
  const formData = new FormData()
  formData.append('audio', file)
  formData.append('language', 'fr')

  const res = await fetch(`${API_BASE}/stt`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Transcription failed' }))
    throw new Error(err.detail || 'STT failed')
  }
  const data = await res.json()
  return data.text
}

// ─── Component ───────────────────────────────────────

export function MarioView() {
  const { t } = useI18n()
  const [status, setStatus] = useState<MarioStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Conversation state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  // TTS state
  const [ttsText, setTtsText] = useState('')
  const [ttsLoading, setTtsLoading] = useState(false)
  const [ttsMessage, setTtsMessage] = useState<string | null>(null)

  // STT state
  const [sttFile, setSttFile] = useState<File | null>(null)
  const [sttLoading, setSttLoading] = useState(false)
  const [sttResult, setSttResult] = useState<string | null>(null)

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
  }, [chatMessages])

  const handleSendChat = useCallback(async () => {
    const msg = chatInput.trim()
    if (!msg || chatLoading) return

    setChatMessages((prev) => [...prev, { role: 'user', content: msg }])
    setChatInput('')
    setChatLoading(true)

    try {
      const response = await sendConversation(msg)
      setChatMessages((prev) => [...prev, { role: 'assistant', content: response }])
    } catch (e: any) {
      setChatMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `❌ ${e.message}` },
      ])
    } finally {
      setChatLoading(false)
    }
  }, [chatInput, chatLoading])

  const handleSpeak = useCallback(async () => {
    const text = ttsText.trim()
    if (!text || ttsLoading) return

    setTtsLoading(true)
    setTtsMessage(null)

    try {
      const ok = await speakText(text)
      setTtsMessage(ok ? '🔊 Mario a parlé !' : '❌ Échec de la synthèse vocale')
    } catch (e: any) {
      setTtsMessage(`❌ ${e.message}`)
    } finally {
      setTtsLoading(false)
    }
  }, [ttsText, ttsLoading])

  const handleTranscribe = useCallback(async () => {
    if (!sttFile || sttLoading) return

    setSttLoading(true)
    setSttResult(null)

    try {
      const text = await transcribeAudio(sttFile)
      setSttResult(text)
    } catch (e: any) {
      setSttResult(`❌ ${e.message}`)
    } finally {
      setSttLoading(false)
    }
  }, [sttFile, sttLoading])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendChat()
    }
  }

  // ── Loading state ────────────────────────────────
  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex-1 p-8 flex items-center justify-center"
      >
        <div className="text-center">
          <div className="text-4xl mb-4 animate-bounce">🎙️</div>
          <p className="text-[var(--text-muted)]">Connexion à Mario...</p>
        </div>
      </motion.div>
    )
  }

  // ── Error / Not available ────────────────────────
  if (error || (!loading && !status?.available)) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex-1 p-8 flex items-center justify-center"
      >
        <div className="max-w-md text-center">
          <div className="text-6xl mb-6">🎙️</div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-3">
            Mario n&apos;est pas disponible
          </h2>
          <p className="text-[var(--text-muted)] mb-4">
            L&apos;assistant vocal Mario n&apos;a pas pu être initialisé.
            Vérifie que le projet Mario est bien présent dans{' '}
            <code className="text-[var(--accent)]">~/Documents/GitHub/Mario</code>
            {' '}et que ses dépendances sont installées.
          </p>
          {error && (
            <p className="text-sm text-red-400 bg-red-400/10 rounded-lg p-3">
              {error}
            </p>
          )}
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
            Réessayer
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
          <span className="text-3xl">🎙️</span>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">Mario</h1>
            <p className="text-sm text-[var(--text-muted)]">
              Assistant Vocal Intelligent — Intégré dans UI-Pro
            </p>
          </div>
        </div>

        {/* Service Status Badges */}
        <div className="flex flex-wrap gap-3 mt-4">
          <StatusBadge label="TTS" active={!!status?.tts} />
          <StatusBadge label="STT" active={!!status?.stt} />
          <StatusBadge label="LLM" active={!!status?.llm} detail={status?.llm_service} />
          <StatusBadge label="Voices" count={status?.voices?.length} />
          <StatusBadge label="Models" count={status?.models?.length} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Left Column: Chat ─────────────────────── */}
        <div className="glass-panel rounded-2xl overflow-hidden flex flex-col h-[500px]">
          <div className="px-5 py-4 border-b border-[var(--border-subtle)] flex items-center gap-2">
            <span>💬</span>
            <span className="font-semibold text-sm text-[var(--text-primary)]">
              Conversation avec Mario
            </span>
            <span className="ml-auto text-[10px] text-[var(--text-muted)] font-mono bg-[var(--surface-secondary)] px-2 py-0.5 rounded">
              {status?.llm_service || 'offline'}
            </span>
          </div>

          {/* Chat messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chatMessages.length === 0 && (
              <div className="text-center text-[var(--text-muted)]/60 text-sm py-12 italic">
                Envoie un message à Mario pour commencer...
              </div>
            )}
            {chatMessages.map((msg, i) => (
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

          {/* Chat input */}
          <div className="p-4 border-t border-[var(--border-subtle)]">
            <div className="flex gap-2">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Parle à Mario..."
                disabled={chatLoading}
                className="flex-1 px-4 py-2.5 rounded-xl bg-[var(--surface-secondary)] border border-[var(--border-subtle)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]/50 outline-none focus:ring-2 focus:ring-violet-500/30 transition-all"
              />
              <button
                onClick={handleSendChat}
                disabled={chatLoading || !chatInput.trim()}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white text-sm font-medium disabled:opacity-40 hover:from-violet-700 hover:to-fuchsia-700 transition-all shrink-0"
              >
                Envoyer
              </button>
            </div>
          </div>
        </div>

        {/* ── Right Column: TTS + STT ──────────────── */}
        <div className="space-y-6">
          {/* TTS Card */}
          <div className="glass-panel rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <span>🗣️</span>
              <h3 className="font-semibold text-sm text-[var(--text-primary)]">
                Synthèse Vocale (TTS)
              </h3>
              <StatusBadge label="" active={!!status?.tts} size="sm" />
            </div>

            <textarea
              value={ttsText}
              onChange={(e) => setTtsText(e.target.value)}
              placeholder="Texte à prononcer par Mario..."
              rows={3}
              className="w-full px-4 py-3 rounded-xl bg-[var(--surface-secondary)] border border-[var(--border-subtle)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]/50 outline-none focus:ring-2 focus:ring-violet-500/30 transition-all resize-none"
            />

            <button
              onClick={handleSpeak}
              disabled={ttsLoading || !ttsText.trim() || !status?.tts}
              className="mt-3 w-full px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-sm font-medium disabled:opacity-40 hover:from-emerald-700 hover:to-teal-700 transition-all"
            >
              {ttsLoading ? '🔊 Mario parle...' : '🔊 Faire parler Mario'}
            </button>

            {ttsMessage && (
              <p className="mt-2 text-xs text-[var(--text-muted)]">{ttsMessage}</p>
            )}
          </div>

          {/* STT Card */}
          <div className="glass-panel rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <span>🎤</span>
              <h3 className="font-semibold text-sm text-[var(--text-primary)]">
                Reconnaissance Vocale (STT)
              </h3>
              <StatusBadge label="" active={!!status?.stt} size="sm" />
            </div>

            <div className="border-2 border-dashed border-[var(--border-subtle)] rounded-xl p-6 text-center">
              <input
                type="file"
                accept="audio/*"
                onChange={(e) => setSttFile(e.target.files?.[0] || null)}
                className="hidden"
                id="stt-file-input"
              />
              <label
                htmlFor="stt-file-input"
                className="cursor-pointer block"
              >
                <div className="text-3xl mb-2">🎵</div>
                <p className="text-sm text-[var(--text-muted)] mb-1">
                  {sttFile ? sttFile.name : 'Clique pour uploader un fichier audio'}
                </p>
                <p className="text-[10px] text-[var(--text-muted)]/50">
                  WAV, MP3, OGG, M4A supportés
                </p>
              </label>
            </div>

            {sttFile && (
              <button
                onClick={handleTranscribe}
                disabled={sttLoading}
                className="mt-3 w-full px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 text-white text-sm font-medium disabled:opacity-40 hover:from-amber-700 hover:to-orange-700 transition-all"
              >
                {sttLoading ? '🔄 Transcription...' : '📝 Transcrire'}
              </button>
            )}

            {sttResult && (
              <div className="mt-3 p-3 rounded-xl bg-[var(--surface-secondary)] text-sm text-[var(--text-primary)]">
                {sttResult}
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ─── Status Badge ──────────────────────────────────

function StatusBadge({
  label,
  active,
  detail,
  count,
  size = 'md',
}: {
  label: string
  active?: boolean
  detail?: string
  count?: number
  size?: 'sm' | 'md'
}) {
  const textSize = size === 'sm' ? 'text-[10px]' : 'text-xs'
  const py = size === 'sm' ? 'py-0.5' : 'py-1'

  return (
    <span
      className={`inline-flex items-center gap-1.5 ${textSize} font-medium ${py} px-2.5 rounded-full border ${
        active !== undefined
          ? active
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            : 'bg-red-500/10 text-red-400 border-red-500/20'
          : 'bg-[var(--surface-secondary)] text-[var(--text-muted)] border-[var(--border-subtle)]'
      }`}
    >
      {active !== undefined && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            active
              ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]'
              : 'bg-red-400'
          }`}
        />
      )}
      {label && <span>{label}</span>}
      {detail && <span className="opacity-70">({detail})</span>}
      {count !== undefined && <span>{count} dispo</span>}
    </span>
  )
}
