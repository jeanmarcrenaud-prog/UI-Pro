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
| @tanstack/react-query | ^5 | Data fetching |

---

## Scripts

```bash
npm run dev      # Development server
npm run build   # Production build
npm run start   # Production server
npm run lint    # ESLint
```