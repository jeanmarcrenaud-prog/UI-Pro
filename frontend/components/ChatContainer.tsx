// components/chat/ChatContainer.tsx
'use client'

import { useState, useCallback, useMemo } from 'react'
import type { Message, AgentStep } from '@/lib/types'
import { useChat } from '@/hooks/useChat'
import { ChatMessages } from './chat/ChatMessages'
import { ChatSuggestions } from './chat/ChatSuggestions'
import { ExamplesList } from './chat/ExamplesList'
import { LoadingIndicator } from './chat/LoadingIndicator'
import { StepProgress } from './chat/StepProgress'
import { StreamingTokenGraph } from './chat/StreamingTokenGraph'
import { motion, AnimatePresence } from 'framer-motion'
import { useI18n } from '@/lib/i18n'
import { useEnableThinking } from './settings/hooks/useEnableThinking'

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
  // Cosmetic indicator on the send button — a small brain emoji when
  // thinking-mode is OFF reminds the operator that the model will
  // jump straight to the answer (no internal chain-of-thought).
  // Hidden when thinking is ON to keep the button focused on the
  // primary action.
  const { enabled: thinkingEnabled } = useEnableThinking()
  const thinkingOff = !thinkingEnabled

  const [inputValue, setInputValue] = useState('')

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

    sendMessage(trimmed)
    setInputValue('')
  }, [inputValue, isLoading, sendMessage])

  const handleExampleSelect = useCallback((prompt: string) => {
    sendMessage(prompt)
  }, [sendMessage])

  const handleSuggestion = useCallback((messageId: string, prompt: string) => {
    // Prepend the suggestion prompt to the existing message content
    const message = messages.find(m => m.id === messageId)
    if (!message?.content) return
    
    // Prepend to input for review instead of sending immediately
    const enhancedPrompt = prompt + message.content
    setInputValue(enhancedPrompt)
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

  return (
    <div className="flex flex-col h-full">
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
            <ChatMessages messages={messages} onSuggestion={handleSuggestion} onRegenerate={regenerate} />
          )}
        </AnimatePresence>

        {/* Step Progress */}
        <AnimatePresence>
          {agentSteps.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
            >
              <StepProgress steps={agentSteps} locale={locale} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Loading / Streaming Indicators */}
        <AnimatePresence>
          {isLoading && !showStreamingIndicator && (
            <LoadingIndicator label={t.loading?.dots || 'Thinking...'} />
          )}

          {showStreamingIndicator && (
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

      {/* Input Area */}
      <div className="sticky bottom-0 bg-gradient-to-t from-[var(--bg-primary)] via-[var(--bg-primary)] to-transparent pt-6 pb-8 px-6 border-t border-[var(--border-subtle)]">
        <div className="max-w-4xl mx-auto">
          <div className="relative bg-slate-900 rounded-3xl border border-slate-700 focus-within:border-violet-500 transition-colors">
            <textarea
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