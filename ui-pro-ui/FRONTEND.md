# Frontend Architecture

> UI-Pro Next.js frontend architecture and folder structure.

## Folder Structure

```
ui-pro-ui/
├── app/              # Next.js app router pages
├── components/       # UI pure components (buttons, inputs, layout)
├── features/        # Feature modules with business logic
├── hooks/           # Custom React hooks
├── lib/             # Core utilities, types, stores
│   ├── stores/     # Zustand stores (chat, agent, UI)
│   ├── types.ts    # TypeScript types
│   └── events.ts   # Event constants
├── services/       # API clients (HTTP, WebSocket, SSE)
├── public/          # Static assets
└── hooks/          # Custom hooks
```

## Directory Role

### app/
Next.js App Router pages.
- `page.tsx` → Main chat interface
- `layout.tsx` → Root layout with providers

### components/
Pure UI components - no business logic.
- Buttons, inputs, cards
- Presentation only

### features/
Business logic modules (ChatInput, AgentSteps, etc.)
- Contains feature-specific components
- Uses services and stores

### services/
API communication layer.
- `chatService.ts` → REST API calls
- `streamService.ts` → WebSocket streaming
- `agentService.ts` → Agent operations
- `modelDiscovery.ts` → Ollama/LM Studio discovery

### lib/
Core utilities.
- **stores/** → Zustand state management
  - `chatStore.ts` → Messages, connection state
  - `agentStore.ts` → Agent configuration
  - `uiStore.ts` → UI state (theme, sidebar)
- **types.ts** → TypeScript interfaces
- **events.ts** → Event constants (TOKEN, STEP, TOOL, DONE, ERROR)

### hooks/
Custom React hooks.
- `useChat.ts` → Chat operations
- `useStream.ts` → Stream handling

---

## Message Flow

```
User Input (TextField)
    ↓
features/chat/chatController
    ↓
services/streamService (WebSocket)
    ↓
hooks/useStream (event handler)
    ↓
stores/chatStore (state update)
    ↓
components/ (react re-render)
```

### Detailed Flow

1. **Input**: User types message in `ChatInput`
2. **Submit**: `handleSubmit` called
3. **Service**: `streamService.send(message)` opens WebSocket
4. **Stream**: Events received via `onmessage`
5. **Parse**: `useStream` parses events (STEP, TOKEN, TOOL, ERROR)
6. **Store**: `chatStore.addMessage()` updates state
7. **Render**: Components re-render with new data

---

## Stores (Zustand)

### chatStore
```typescript
interface ChatState {
  messages: Message[]
  isConnected: boolean
  isStreaming: boolean
  selectedModel: string
  lastError: string | null
  
  addMessage: (msg: Message) => void
  setConnected: (status: boolean) => void
  setStreaming: (status: boolean) => void
  setError: (error: string | null) => void
}
```

### agentStore
```typescript
interface AgentState {
  context: string
  temperature: number
  maxTokens: number
  streaming: boolean
  
  setConfig: (config: Partial<AgentState>) => void
}
```

### uiStore
```typescript
interface UIState {
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  compactMode: boolean  // Dense message history
  
  toggleTheme: () => void
  toggleSidebar: () => void
  toggleCompact: () => void
}
```

---

## Event Types

Defined in `lib/events.ts`:

```typescript
export const WS_EVENTS = {
  TOKEN: 'token',     // LLM token streaming
  STEP: 'step',      // Agent step (analyzing, planning, ...)
  TOOL: 'tool',     // Tool execution
  DONE: 'done',     // Completion
  ERROR: 'error',  // Error
} as const;
```

### Parsed Events

```typescript
interface StreamEvent {
  type: 'token' | 'step' | 'tool' | 'done' | 'error'
  data: string
  timestamp: number
}
```

---

## Services

### streamService.ts
WebSocket connection management.

```typescript
// Connect
const ws = streamService.connect()

// Send message
ws.send({ message: "Create a file" })

// Events
ws.onmessage = (event) => {
  const parsed = parseEvent(event.data)
  // → { type: 'step', data: 'Planning...', timestamp: ... }
}
```

### chatService.ts
REST API calls.

```typescript
// POST /api/chat
const response = await chatService.send({
  message: "Create hello.py"
})
```

---

## Error Handling

Errors are handled at store level:

```typescript
// In any component
chatStore.setError("Connection failed")

// Global error display subscribes to store
const { lastError } = useStore(chatStore)

if (lastError) {
  return <Toast message={lastError} />
}
```

---

## Compact Mode

Toggle in `uiStore` for dense history:

```typescript
const { compactMode, toggleCompact } = useStore(uiStore)

// Compact: timestamp only, no full date
// Normal: full date + time
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| next | 14+ | App Router |
| react | 18+ | UI |
| zustand | ^4 | State management |
| tailwind | ^3 | Styling |
| framer-motion | ^11 | Animations |
| react-markdown | ^10 | Markdown rendering |
| react-syntax-highlighter | ^16 | Code syntax highlighting |

---

## Scripts

```bash
npm run dev      # Development server (port 3000)
npm run build   # Production build
npm run start   # Production server
npm run lint    # ESLint
```

---

## Recent Fixes (2026)

### Loading State Fix
The chat was showing "Generating..." then stopping. Fixed by:
- Waiting for `msg.status === 'done'` before calling `setLoading(false)`
- Saving history only after response is complete

### React Key Warnings
Fixed duplicate keys in several components:
- `ChatContainer.tsx`: `key={example.prompt}` instead of `key={i}`
- `ChatMessages.tsx`: `key={msg.id || \`msg-${index}\`}`
- `DebugPanel.tsx`: Added `key="debug-info"` for AnimatePresence
- `Sidebar.tsx`: Fixed model option keys

### History Persistence
Chat history now auto-saves to localStorage via Zustand persist middleware.

### Download Improvements
Intelligent filename extraction from code content:
- Looks for `class`, `def`, `function`, `const`, etc.
- Falls back to timestamp-based name
- Supports 20+ languages with proper extensions

### Auto-Detect Code Blocks
Added `preprocessContent()` to MarkdownRenderer that automatically detects code-like text and wraps in markdown code blocks:
- Detects patterns: `def`, `class`, `function`, `const`, `let`, `import`, `if`, `for`, `while`, etc.
- Auto-detects language: python, javascript, html
- Enables download button (💾) for plain text code

### MarkdownRenderer Performance & UX (v2)
Major refactor with improvements:
- **memo + useMemo** → Prevents unnecessary re-renders
- **remark-gfm** → Better markdown support (tables, strikethrough, etc.)
- **Improved code detection** → More patterns, better language detection
- **Better styling** → rounded-xl, border-slate-700, bg-slate-800/70
- **Cleaner components** → Separated CodeComponent and PreComponent

### Memory Leak Prevention
Added limits to prevent OOM crashes:
- Messages array: max 100 in memory
- Logs: max 100 entries
- Chat history: max 50 chats
- Resume message history: max 20 entries
- Backend sessions: max 50
- Backend errors: max 50

### WebSocket Resume Support
Implemented auto-reconnect with resume capability:
- Frontend sends `last_chunk_index` on reconnect
- Backend tracks active requests per message_id
- Skips already-sent chunks during resume
- Max 5 reconnect attempts with exponential backoff

### TypeScript Fixes in useChat.ts
Fixed type comparison errors:
- `msg.status === 'completed'` → `msg.status === 'done'`
- Removed invalid `msg.type === 'done'` check
- Map `MessageStatus` to `AgentStepStatus` properly

---

## Bugs Fixed (April 2026)

This section documents all bugs that were identified and fixed in the frontend codebase.

### Critical Bugs

| # | File | Bug Description | Root Cause | Fix |
|-----|------|----------------|-----------|------|
| 1 | `app/page.tsx` | useEffect code orphaned outside if block - timer and model logging never executed | Bad indentation after `if (isLoading)` | Fixed indentation |
| 2 | `app/page.tsx` | `hasError?` without space - syntax error | Missing ternary space | Added space `hasError ?` |
| 3 | `components/ChatContainer.tsx` | DOM-read anti-pattern for input value | `textarea.value` reads bypass React state | Added controlled input with `useState` |

### WebSocket Bugs (chatService.ts)

| # | Bug Description | Root Cause | Fix |
|-----|----------------|-----------|------|
| 4 | `ws://${host}:8000` where `host` could be empty string | `window.location.hostname` returns empty string on localhost | Added `\|\| 'localhost'` fallback |
| 5 | 8s timeout on connect Promise | No timeout caused hang on failed connection | Added `Promise.race` with timeout |
| 6 | `onerror` called `resolve()` instead of `reject()` | Errors silently ignored, invalid responses sent | Changed to `reject()` |
| 7 | `fallback()` content could be undefined | Proxy returned `{model_fast}` not array | Added safe fallback string |
| 8 | Clean close detected but reconnects not reset | `ev.code >= 1000` missed some clean codes | Increased to 6 reconnects with better detection |
| 9 | `fallback()` URL construction wrong | Empty `host` passed to URL | Fixed URL construction |

### Model Discovery Bugs (modelDiscovery.ts)

| # | Bug Description | Root Cause | Fix |
|-----|----------------|-----------|------|
| 10 | `AbortSignal.timeout()` not supported in all browsers | Safari/Firefox older versions | Replaced with `AbortController` |
| 11 | Wrong Ollama fallback endpoint | Proxy returns `{model_fast}` not model array | Added proxy format detection, returns empty array |
| 12 | User model selection ignored | Empty string treated as valid model | Added falsy check `\|\| undefined` |

### Component Bugs

| # | File | Bug Description | Root Cause | Fix |
|-----|------|----------------|-----------|------|
| 13 | `SettingsView.tsx` - settings never loaded | `hasLoaded` never set to `true` | Added `setHasLoaded(true)` in mount effect |
| 14 | `HistoryView.tsx` - crash on undefined messages | `messages.length` when `messages` undefined | Added optional chaining |
| 15 | `HistoryView.tsx` - confirm-delete race condition | `setTimeout` caused race on remount | Removed setTimeout, direct delete |
| 16 | `CodeBlock.tsx` - `as any` type suppression | Type workaround for SyntaxHighlighter | Added proper `CodeBlockProps` interface |
| 17 | `DebugPanel.tsx` - progress bar on error | Showed on `status === 'error'` | Changed to only show on `status === 'running'` |
| 18 | `DebugPanel.tsx` - error section always shown | Showed regardless of status | Changed to only show on `status === 'error'` |
| 19 | `DebugPanel.tsx` - unstable step keys | Used step index only | Added `${step.id}-${i}` for stability |
| 20 | `useChat.ts` - empty string handled wrong | `message_id === ""` compared incorrectly | Added empty string guard |

### File Cleanup

- **Deleted**: `components/chat/ChatContainer.tsx` - duplicate file never imported, created confusion

### TypeScript Bugs (useChat.ts)

| # | Bug Description | Root Cause | Fix |
|-----|----------------|-----------|------|
| 21 | `msg.status === 'completed'` type error | `'completed'` not in `MessageStatus` type | Changed to `msg.status === 'done'` |
| 22 | `msg.type === 'done'` type error | `msg.type` is `'step'` not `'done'` | Removed redundant check |
| 23 | Step status mapping error | `MessageStatus` not assignable to `AgentStepStatus` | Added explicit mapping: `'done'`→`'done'`, otherwise `'active'` |

### Backend Memory Bugs

| # | Bug Description | Root Cause | Fix |
|-----|----------------|-----------|------|
| 24 | Unlimited `_errors` list | No size limit on `ThreadSafeStore` | Kept only last 50 errors |
| 25 | Unlimited WebSocket sessions | No cleanup on session limits | Max 50 sessions, removes oldest |
| 26 | `chunk_size: 1` causes OOM | Each token = 1 WebSocket message | Batch 5 tokens per message |

### Known Limitations

- `AbortController` requires manual abort signal management vs `AbortSignal.timeout()` simpler API
- WebSocket fallback to HTTP may have latency on first request
- Model discovery polls backend every 5s - could be improved with SSE for live updates
- Some older browsers don't support `Array.at()` - using index notation instead