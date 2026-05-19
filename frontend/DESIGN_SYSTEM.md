# UI-Pro Design System Documentation

## 🎨 Overview

This is the official design system for UI-Pro - a SaaS-level, ChatGPT-like AI chat interface built with Next.js 16, React 18, Tailwind CSS 4, and TypeScript.

---

## 📁 File Structure (Recommended)

```
ui-pro-ui/
├── app/                          # Next.js App Router
│   ├── (chat)/                   # Grouped routes
│   │   ├── page.tsx              # Main chat interface
│   │   └── layout.tsx
│   ├── layout.tsx
│   └── globals.css
├── components/                   # Reusable, presentational UI
│   ├── ui/                       # Primitive components (Button, Input, Card, etc.)
│   ├── chat/                     # Chat-specific UI (MessageBubble, ChatInput, etc.)
│   └── common/                   # Layout, Toast, MarkdownRenderer, CodeBlock
├── features/                     # Feature modules (business logic + smart components)
│   ├── chat/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── store.ts              # Or slice in global store
│   ├── agent/
│   └── settings/
├── hooks/                        # Custom hooks
│   ├── useChat.ts
│   ├── useStream.ts
│   ├── useWebSocket.ts           # Recommended: dedicated WS hook
│   └── useModelDiscovery.ts
├── lib/
│   ├── stores/                   # Zustand stores
│   │   ├── chatStore.ts
│   │   ├── agentStore.ts
│   │   └── uiStore.ts
│   ├── types/
│   ├── events.ts
│   ├── utils.ts
│   └── constants.ts
├── services/                     # API layer
│   ├── api.ts                    # REST client (fetch wrapper)
│   ├── streamService.ts          # WebSocket / SSE abstraction
│   ├── chatService.ts
│   └── modelDiscovery.ts
├── public/
└── types/                        # Global TypeScript definitions (if needed)
```

---

## Key Recommendations

### 1. Streaming Layer (services/streamService.ts + hooks/useStream.ts)

Your backend guarantees one final event (`done` / `error` / `cancelled`). Leverage that.

**Best practice:**

- Abstract WebSocket / SSE behind a single service that normalizes events to `StreamChunk`-like shape
- Use a dedicated `useWebSocket` hook with:
  - Exponential backoff reconnection (max 6 attempts)
  - Heartbeat (ping/pong every 25s)
  - Resume capability using `stream_id` + `last_index`
  - Proper cleanup on unmount

### 2. Zustand Stores

Keep them focused. Consider Zustand slices or create multiple stores for better scalability.

**Add to chatStore:**

```typescript
currentStreamId: string | null
abortCurrentStream: () => void
resumeFromIndex: (index: number) => void
```

### 3. Event Handling

Update `lib/events.ts`:

```typescript
export const STREAM_EVENTS = {
  TOKEN: 'token',
  STEP: 'step',
  TOOL: 'tool',
  DONE: 'done',
  ERROR: 'error',
  CANCELLED: 'cancelled',
} as const;

export type StreamEventType = typeof STREAM_EVENTS[keyof typeof STREAM_EVENTS];
```

In `useStream.ts`, map backend `StreamChunk.to_dict()` directly and handle the guaranteed final event to set `isStreaming: false`.

### 4. Cancellation

Since your backend supports `cancel_stream(stream_id)`, expose a clean `stopGeneration()` that sends a cancellation message over WebSocket and calls the service.

### 5. SSE vs WebSocket

For pure token streaming + steps:

- **SSE** is often simpler, more reliable (auto-reconnect), and sufficient
- Use **WebSocket** only if you need real bidirectional features (immediate cancel, tool calls, multiple concurrent streams)

Many production LLM UIs use SSE for the stream and a separate lightweight WS for control signals.

---

## Quick Wins & Improvements

| Area | Improvement |
|------|-------------|
| **Type Safety** | Create shared `StreamEvent` interface matching backend `StreamChunk.to_dict()` |
| **Performance** | Continue using `React.memo` + `useMemo` in `MarkdownRenderer` and `CodeBlock` |
| **Resume Logic** | On reconnect, send `{ action: "resume", stream_id, last_index }` — backend already tracks active streams |
| **Error UX** | Centralize error display using Toast component subscribed to `chatStore.lastError` |
| **Loading States** | Only stop "Generating..." indicator when terminal event received (`done`, `error`, or `cancelled`) |

---

## 🎨 UI/UX Principles

### Visual Design

| Element | Value |
|---------|-------|
| **Primary Color** | `#6366f1` (Indigo-500) |
| **Background** | `#0f172a` (Slate-900) |
| **Surface** | `#1e293b` (Slate-800) |
| **Text Primary** | `#f1f5f9` (Slate-100) |
| **Text Secondary** | `#94a3b8` (Slate-400) |
| **Border** | `#334155` (Slate-700) |
| **Accent** | `#22c55e` (Green-500 for success) |

### Spacing System

- Base unit: `4px`
- Common values: `4`, `8`, `12`, `16`, `24`, `32`, `48`

### Typography

| Element | Font | Size | Weight |
|--------|------|------|--------|
| **Heading 1** | Inter | 24px | 600 |
| **Heading 2** | Inter | 20px | 600 |
| **Body** | Inter | 14px | 400 |
| **Code** | JetBrains Mono | 13px | 400 |

### Component Patterns

#### Button Variants

- **Primary**: `bg-indigo-600 hover:bg-indigo-700 text-white`
- **Secondary**: `bg-slate-700 hover:bg-slate-600 text-slate-100`
- **Ghost**: `bg-transparent hover:bg-slate-800 text-slate-300`
- **Danger**: `bg-red-600 hover:bg-red-700 text-white`

#### Input Fields

- Background: `bg-slate-800/80`
- Border: `border-slate-700`
- Focus: `ring-2 ring-indigo-500/50`
- Placeholder: `text-slate-500`

---

## 🔧 Technical Stack

| Layer | Technology |
|-------|------------|
| **Framework** | Next.js 16 (App Router) |
| **UI Library** | React 18 |
| **Styling** | Tailwind CSS 4 |
| **Animations** | Framer Motion |
| **State** | Zustand |
| **Types** | TypeScript 5 |
| **Icons** | Lucide React |
| **Markdown** | react-markdown + rehype-highlight |

---

## ♿ Accessibility

- All interactive elements have `aria-label` or accessible name
- Focus visible: `ring-2 ring-indigo-500`
- Color contrast: WCAG AA compliant
- Screen reader live regions for streaming content

---

## 📱 Responsive Breakpoints

| Breakpoint | Width | Layout |
|-----------|-------|--------|
| **Mobile** | < 768px | Single column, bottom nav |
| **Tablet** | 768-1024px | Sidebar collapsed |
| **Desktop** | > 1024px | Full sidebar |

---

## 🔄 State Management

### Zustand Store Structure

```typescript
// lib/stores/chatStore.ts
interface ChatState {
  messages: Message[]
  isStreaming: boolean
  currentStreamId: string | null
  
  addMessage: (msg: Message) => void
  appendToken: (token: string) => void
  setStreaming: (streaming: boolean) => void
  abortCurrentStream: () => void
  resumeFromIndex: (index: number) => void
}

// lib/stores/agentStore.ts
interface AgentState {
  currentStep: number
  steps: AgentStep[]
  isThinking: boolean
  
  setStep: (step: number) => void
  addStep: (step: AgentStep) => void
  setThinking: (thinking: boolean) => void
}

// lib/stores/uiStore.ts
interface UIState {
  activeTab: 'chat' | 'history' | 'settings'
  sidebarOpen: boolean
  
  setActiveTab: (tab: string) => void
  toggleSidebar: () => void
}
```

---

## 🎬 Animations

### Framer Motion Patterns

```typescript
// Fade in
<motion.div
  initial={{ opacity: 0 }}
  animate={{ opacity: 1 }}
  exit={{ opacity: 0 }}
/>

// Slide up
<motion.div
  initial={{ opacity: 0, y: 10 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.2 }}
/>

// Typing cursor
<motion.span
  animate={{ opacity: [0, 1, 0] }}
  transition={{ repeat: Infinity, duration: 0.8 }}
/>
```

---

## 📦 Bundle Optimization

- Use `next/dynamic` for lazy loading heavy components
- Code split by route
- Prefer `import` statements over require
- Use `turbopack` in development

---

## 🧪 Testing Strategy

| Test Type | Tool | Coverage Target |
|----------|------|--------------|
| **Unit** | Vitest | Utility functions, hooks |
| **Component** | Testing Library | UI components |
| **E2E** | Playwright | Critical flows |

---

## 📖 Documentation Standards

- JSDoc for public APIs
- TypeScript interfaces documented
- README in each major directory
- Component prop tables in Storybook

---

## 🔐 Security

- No API keys in client code
- Sanitize user input in markdown rendering
- Escape HTML in code blocks
- CSP headers configured

---

## 🚀 Deployment

| Environment | Target |
|-------------|-------|
| **Development** | `localhost:3000` |
| **Staging** | Vercel Preview |
| **Production** | Vercel |

Environment variables:
- `NEXT_PUBLIC_API_URL` - Backend URL
- `NEXT_PUBLIC_WS_URL` - WebSocket URL