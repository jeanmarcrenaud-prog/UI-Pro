// components/chat/ChatContainer.tsx
'use client'

import { useState, useCallback, useMemo, useRef, useEffect } from 'react'
import type { Message, AgentStep } from '@/lib/types'
import { useChat } from '@/hooks/useChat'
import { ChatMessages } from './chat/ChatMessages'
import { ChatSuggestions } from './chat/ChatSuggestions'
import { ExamplesList } from './chat/ExamplesList'
import { LoadingIndicator } from './chat/LoadingIndicator'
import { StepProgress } from './chat/StepProgress'
import { StreamingTokenGraph } from './chat/StreamingTokenGraph'
import { TerminalPanel, type TerminalOutputLine } from './chat/TerminalPanel'
import { motion, AnimatePresence } from 'framer-motion'
import { useI18n } from '@/lib/i18n'
import { useEnableThinking } from './settings/hooks/useEnableThinking'
import { events } from '@/lib/events'
import { AgentCanvas } from '@/components/agent/AgentCanvas'
import { useUIStore } from '@/lib/stores/uiStore'

const DEFAULT_EXAMPLES = [
  {
    icon: '🐍',
    text: 'Python weather script',
    prompt: `Write a Python 3.10+ script that fetches current weather for Paris (48.85, 2.35) from the Open-Meteo API.

Requirements:
- Use only stdlib (urllib.request, json) — no requests/httpx
- 10s timeout on the HTTP request
- Catch and report network errors, HTTP errors, and JSON parse errors with distinct messages
- Output a formatted table to stdout: city, temperature (°C), wind speed (km/h), humidity (%)
- Include type hints and a if __name__ == "__main__" guard`,
  },
  {
    icon: '📊',
    text: 'Analyze code for issues',
    prompt: `Analyze the following Python function for performance and correctness.

For each issue you find, output:
1. Line number and a one-line description
2. Impact (time complexity, correctness, etc.)
3. Concrete fix (code)

Focus on: time complexity, edge cases (n=0, n=1, negative input), memoization opportunities, recursion depth limits, integer overflow, off-by-one errors.

{code}`,
  },
  {
    icon: '🔧',
    text: 'FastAPI CRUD app',
    prompt: `Build a complete FastAPI CRUD application for a todo list (single file, runnable).

Pydantic v2 models:
- Todo: id (UUID4), title (str, min 1, max 200), done (bool, default false), created_at (datetime)
- TodoCreate: title only
- TodoUpdate: all fields optional

Endpoints (use proper status codes: 200, 201, 204, 404):
- GET /todos?done=&skip=&limit=
- POST /todos → 201
- GET /todos/{id} → 200 or 404
- PATCH /todos/{id} → 200 or 404
- DELETE /todos/{id} → 204

Storage: in-memory dict keyed by UUID (no database).
Also: CORS for http://localhost:3000, automatic /docs, /health returning {"status": "ok"}.`,
  },
  {
    icon: '🎨',
    text: 'React TypeScript component',
    prompt: `Write a TodoList React TypeScript component.

Props: { initialItems?: Todo[]; onCountChange?: (count: number) => void }
Types: Todo = { id: string; title: string; done: boolean }

State: items (Todo[]), inputValue (string)
Persistence: localStorage under key "todos" (load on mount, save on change)

Features:
- Add on Enter key
- Delete with inline confirmation (click again within 2s to confirm)
- Toggle done via checkbox
- Empty state: "No items yet" message

Style: Tailwind CSS, dark theme (slate-800/900 base, violet-500 accent).
Accessibility: aria-labels, keyboard navigation, focus visible.`,
  },
  {
    icon: '🧪',
    text: 'Pytest unit tests',
    prompt: `Write pytest unit tests for an email validation function.

Test categories (use @pytest.mark.parametrize):
- Valid: standard, plus-addressing, subdomains, international
- Invalid format: missing @, missing local part, missing domain, spaces, multiple @
- Edge cases: empty string, single char, very long (255+), unicode, IDN
- Performance: 10,000 validations complete in under 100ms

Conventions:
- One test function per behavior
- Fixtures for shared setup (valid email generator, etc.)
- Assert specific exception types and messages
- Use tmp_path for any filesystem side effects

Aim for 80%+ line coverage of the function under test.

{code}`,
  },
  {
    icon: '🌐',
    text: 'TypeScript debounce',
    prompt: `Write a TypeScript debounce utility with cancellation.

Signature:
  debounce<T extends (...args: any[]) => void>(
    fn: T,
    delay: number
  ): T & { cancel: () => void; flush: () => void }

Behavior:
- Calls fn after \`delay\` ms of inactivity; subsequent calls reset the timer
- cancel(): clears the pending timer, no further call
- flush(): invokes fn immediately with the latest args, clears the timer
- Preserves \`this\` binding (call/apply through to fn)
- Public API must be type-safe (no \`any\` in exported types)

Include JSDoc for each method and one usage example.`,
  },
  {
    icon: '📦',
    text: 'Modern Python package',
    prompt: `Create a modern Python package layout for "mytool" (use src/ layout, PEP 621).

Files to create:
- pyproject.toml (setuptools backend, no setup.py)
- README.md (one-paragraph description + usage)
- src/mytool/__init__.py
- src/mytool/py.typed (empty marker file)
- src/mytool/core.py (one example function: greet(name: str) -> str)
- tests/test_core.py (one test for greet)
- .gitignore (Python + build artifacts)

pyproject.toml must declare:
- [project]: name, version="0.1.0", description, readme, requires-python=">=3.10", license, authors
- [project.optional-dependencies]: dev = ["pytest", "ruff"]
- [build-system]: requires=["setuptools>=68"], build-backend="setuptools.build_meta"
- [tool.setuptools.packages.find]: where = ["src"]
- [tool.pytest.ini_options]: testpaths = ["tests"]
- [tool.ruff]: line-length = 100, target-version = "py310"`,
  },
  {
    icon: '🔒',
    text: 'FastAPI JWT auth',
    prompt: `Write a FastAPI JWT authentication module.

Dependencies: PyJWT (lighter than python-jose for HS256, no crypto extras)

Components:
1. create_access_token(data: dict, expires_delta: timedelta) -> str
   - HS256, includes iat, exp, sub claims
   - Secret from settings.secret_key
2. get_current_user(authorization: str = Header()) -> User
   - Reads "Authorization: Bearer <token>"
   - Validates signature + expiration
   - Returns User with id (from sub), scopes (from "scopes" claim)
   - Errors: 401 with WWW-Authenticate: Bearer header for missing/invalid/expired
3. POST /login (form: username, password) -> {access_token, token_type}
   - Demo credentials check (dict), don't use a real DB
   - Returns 401 on bad credentials

Include all imports and the User model.`,
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
  const { enabled: thinkingEnabled } = useEnableThinking()
  const thinkingOff = !thinkingEnabled

  const [inputValue, setInputValue] = useState('')
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)
  const canvasView = useUIStore((s) => s.canvasView)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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

    if (editingMessageId) {
      regenerate(editingMessageId, trimmed)
      setEditingMessageId(null)
    } else {
      sendMessage(trimmed)
    }
    setInputValue('')
  }, [inputValue, isLoading, sendMessage, regenerate, editingMessageId])

  const handleExampleSelect = useCallback((prompt: string) => {
    sendMessage(prompt)
  }, [sendMessage])

  const handleSuggestion = useCallback((messageId: string, prompt: string) => {
    const message = messages.find(m => m.id === messageId)
    if (!message?.content) return
    
    const enhancedPrompt = prompt + message.content
    setInputValue(enhancedPrompt)
  }, [messages])

  const handleEdit = useCallback((messageId: string) => {
    const message = messages.find(m => m.id === messageId)
    if (!message) return
    setEditingMessageId(messageId)
    setInputValue(message.content)
    setTimeout(() => {
      textareaRef.current?.focus()
      textareaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
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

  // ── Terminal state ──────────────────────────────────────────────────
  const [execLines, setExecLines] = useState<TerminalOutputLine[]>([])
  const [terminalVisible, setTerminalVisible] = useState(false)

  useEffect(() => {
    const handler = ({ line, channel }: { line: string; channel: string }) => {
      setExecLines(prev => [...prev, { content: line, channel, timestamp: Date.now() }])
    }
    events.on('execOutput', handler)
    return () => events.off('execOutput', handler)
  }, [])

  // Auto-show terminal when first exec line arrives
  useEffect(() => {
    if (execLines.length > 0 && !terminalVisible) {
      setTerminalVisible(true)
    }
  }, [execLines.length, terminalVisible])

  const handleClearTerminal = useCallback(() => {
    setExecLines([])
  }, [])

  const handleToggleTerminal = useCallback(() => {
    setTerminalVisible(prev => !prev)
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Step Progress / Agent Canvas (toggle) - NOW ABOVE MESSAGES */}
      <AnimatePresence mode="wait">
        {agentSteps.length > 0 && (
          <motion.div
            key={canvasView ? 'canvas' : 'list'}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {/* View toggle */}
            {/* View toggle — segmented control */}
            <div className="flex items-center gap-1 mb-1.5">
              <span className="text-[10px] text-slate-600 mr-auto font-mono">
                {canvasView ? 'Agent Canvas' : 'Step Progress'}
              </span>
              <div className="flex bg-slate-800/60 rounded-lg p-0.5 border border-slate-700/50">
                <button
                  onClick={() => useUIStore.getState().setCanvasView(false)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-150 ${
                    !canvasView
                      ? 'bg-violet-500/20 text-violet-300 shadow-sm shadow-violet-500/10'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                  title="List view"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" /><line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
                  </svg>
                  Liste
                </button>
                <button
                  onClick={() => useUIStore.getState().setCanvasView(true)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-150 ${
                    canvasView
                      ? 'bg-violet-500/20 text-violet-300 shadow-sm shadow-violet-500/10'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                  title="Graph view"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                  Graphe
                </button>
              </div>
            </div>

            {canvasView ? (
              <AgentCanvas />
            ) : (
              <StepProgress steps={agentSteps} locale={locale} />
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6 scrollbar-thin scrollbar-thumb-slate-700">
        <AnimatePresence mode="wait">
          {isEmpty ? (
            <ExamplesList
              examples={DEFAULT_EXAMPLES}
              onSelect={handleExampleSelect}
              disabled={isLoading}
            />
          ) : (
            <ChatMessages messages={messages} onSuggestion={handleSuggestion} onRegenerate={regenerate} onEdit={handleEdit} />
          )}
        </AnimatePresence>

        {/* Loading / Streaming Indicators */}
        <AnimatePresence>
          {isLoading && !showStreamingIndicator && agentSteps.length === 0 && (
            <LoadingIndicator label={t.loading?.dots || 'Thinking...'} />
          )}

          {showStreamingIndicator && agentSteps.length === 0 && (
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
                
                <StreamingTokenGraph />
                
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

      {/* Terminal Panel (execution output streaming) */}
      <TerminalPanel
        lines={execLines}
        isVisible={terminalVisible}
        onToggleVisibility={handleToggleTerminal}
        onClear={handleClearTerminal}
      />

      {/* Input Area */}
      <div className="sticky bottom-0 bg-gradient-to-t from-[var(--bg-primary)] via-[var(--bg-primary)] to-transparent pt-6 pb-8 px-6 border-t border-[var(--border-subtle)]">
        <div className="max-w-4xl mx-auto">
          <div className="relative bg-slate-900 rounded-3xl border border-slate-700 focus-within:border-violet-500 transition-colors">
            {editingMessageId && (
              <div className="absolute -top-3 left-4 flex items-center gap-2">
                <span className="text-[11px] text-amber-400 bg-slate-800 px-2 py-0.5 rounded-full border border-amber-500/30">
                  Editing
                </span>
                <button
                  onClick={() => { setEditingMessageId(null); setInputValue('') }}
                  className="text-[11px] text-slate-400 hover:text-white bg-slate-800 px-2 py-0.5 rounded-full border border-slate-600 hover:border-slate-500 transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
            <textarea
              ref={textareaRef}
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
              className={`absolute bottom-4 right-4 ${
                thinkingOff
                  ? 'bg-violet-600 hover:bg-violet-700'
                  : 'bg-blue-600 hover:bg-blue-700'
              } disabled:bg-slate-700 disabled:text-slate-500 text-white px-3.5 py-3 rounded-2xl transition-all disabled:cursor-not-allowed flex items-center gap-1.5`}
              aria-label="Send message"
              title={
                thinkingOff
                  ? 'Send — Thinking mode is OFF (model jumps straight to the answer)'
                  : 'Send — Thinking mode is ON (model may reason internally)'
              }
            >
              {thinkingOff && (
                <motion.span
                  className="text-[11px] leading-none"
                  aria-hidden="true"
                  animate={{ scale: [1, 1.18, 1], opacity: [0.7, 1, 0.7] }}
                  transition={{ repeat: Infinity, duration: 1.8, ease: 'easeInOut' }}
                >
                  🧠
                </motion.span>
              )}
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

ChatContainer.displayName = 'ChatContainer'