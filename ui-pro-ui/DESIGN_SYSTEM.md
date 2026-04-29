# UI-Pro Design System Documentation

## 🎨 Overview

This is the official design system for UI-Pro - a SaaS-level, ChatGPT-like AI chat interface built with Next.js 16, React 18, Tailwind CSS 4, and TypeScript.

---

## 📁 File Structure

```
ui-pro-ui/
├── app/
│   ├── page.tsx            # Main chat page
│   ├── layout.tsx          # Root layout
│   └── globals.css          # Global styles with CSS variables
│
├── components/
│   ├── ui/                    # Atomic UI components
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Input.tsx
│   │   ├── Textarea.tsx
│   │   ├── Select.tsx
│   │   ├── Badge.tsx
│   │   └── index.ts
│   │
│   ├── chat/                  # Chat-specific components
│   │   ├── MessageBubble.tsx
│   │   ├── TypingIndicator.tsx
│   │   ├── ChatMessages.tsx
│   │   ├── AgentSteps.tsx
│   │   ├── StepProgress.tsx
│   │   └── index.ts
│   │
│   └── agent/                 # Agent workflow components
│       ├── StepItem.tsx
│       ├── AgentSteps.tsx
│       └── index.ts
│
├── features/                  # Business logic
│   ├── chat/
│   │   ├── ChatInput.tsx
│   │   └── useChat.ts
│   └── settings/
│       └── SettingsModal.tsx
│
├── services/                  # API layer
│   ├── apiClient.ts       # HTTP client
│   ├── streamService.ts  # WebSocket/SSE streaming
│   └── wsClient.ts       # WebSocket client
│
├── stores/                   # Zustand state management
│   ├── chatStore.ts      # Chat messages, streaming state
│   └── settingsStore.ts # User settings
│
├── lib/
│   ├── constants.ts     # Shared constants
│   ├── types.ts        # TypeScript types
│   └── utils.ts        # Utility functions
│
├── styles/
│   └── tokens.ts      # Design system tokens
│
├── tailwind.config.ts    # Tailwind 4 config
└── package.json
```

---

## 🎨 Design Tokens

### Colors (Dark Theme)

```typescript
bg: {
  primary: '#020617',     // Deep dark background
  secondary: '#0f172a', // Panels and content areas
  tertiary: '#0f172acc', // Overlays
}

surface: {
  primary: '#0f172a',
  secondary: '#1e293b',
  hover: '#334155',
}

border: {
  subtle: '#1e293b',
  default: '#334155',
  strong: '#475569',
}

text: {
  primary: '#f8fafc',
  secondary: '#cbd5e1',
  muted: '#64748b',
  disabled: '#475569',
}

accent: {
  primary: '#8b5cf6',     // Violet (brand)
  hover: '#7c3aed',
  soft: '#8b5cf633',
}

// Status colors
success: '#22c55e'
warning: '#eab308'
error: '#ef4444'
```

### Spacing

| Token | Value |
|-------|-------|
| xs | 4px |
| sm | 8px |
| md | 12px |
| lg | 16px |
| xl | 24px |
| xxl | 32px |

### Typography

| Token | Value |
|-------|-------|
| xs | 12px |
| sm | 13px |
| md | 14px |
| lg | 16px |
| xl | 18px |
| xxl | 20px |

Font: 'Inter, sans-serif'

---

## 🧩 Components

### Button

```tsx
import { Button } from '@/components/ui'

<Button variant="primary" size="md">
  Send
</Button>

<Button variant="secondary" size="sm">
  Cancel
</Button>

<Button variant="ghost" size="lg">
  Learn more
</Button>
```

### Input & Textarea

```tsx
import { Input, Textarea } from '@/components/ui'

<Input
  label="Username"
  error="This field is required"
  helperText="Enter your username"
/>

<Textarea
  label="Task description"
  rows={4}
  placeholder="Describe your task..."
/>
```

### Badge

```tsx
import { Badge } from '@/components/ui'

<Badge variant="success">✓ Success</Badge>
<Badge variant="error">✗ Error</Badge>
<Badge variant="warning">⚠ Warning</Badge>
<Badge variant="processing">⚙️ Processing</Badge>
```

### MessageBubble

```tsx
import { MessageBubble } from '@/components/chat'

<MessageBubble role="user" content="Hello!" />
<MessageBubble 
  role="assistant" 
  content={<AgentSteps />}
/>
```

### AgentSteps

```tsx
import { AgentSteps } from '@/components/chat'

<AgentSteps
  steps={[
    { id: 'analyzing', label: 'Analyzing', status: 'completed' },
    { id: 'planning', label: 'Planning', status: 'active' },
    { id: 'executing', label: 'Executing', status: 'pending' },
    { id: 'reviewing', label: 'Reviewing', status: 'pending' },
  ]}
/>
```

---

## 📦 Stores (Zustand)

### chatStore

```typescript
import { useChatStore } from '@/stores/chatStore'

// State
messages: Message[]
isStreaming: boolean
streamId: string | null

// Actions
addMessage(message: Message)
setStreaming(streaming: boolean)
clearMessages()
```

### settingsStore

```typescript
import { useSettingsStore } from '@/stores/settingsStore'

// State
defaultModel: string
temperature: number
maxTokens: number

// Actions
setDefaultModel(model: string)
setTemperature(temp: number)
```

---

## 📡 API Integration

### HTTP Client

```typescript
import { apiClient } from '@/services/apiClient'

const response = await apiClient.post('/api/chat', {
  message: 'Hello',
  model: 'qwen2.5:7b',
})
```

### Streaming

```typescript
import { streamService } from '@/services/streamService'

for await (const chunk of streamService.connect(prompt)) {
  // StreamStatus: STARTING | GENERATING | COMPLETED | ERROR
  console.log(chunk.text, chunk.status)
}
```

---

## 🚀 Usage

### Installation

```bash
cd ui-pro-ui
npm install
npm run dev
```

### Development Server

```bash
npm run dev
# http://localhost:3000
```

### Build

```bash
npm run build
npm start
```

---

## 🎯 Key Features

- ✅ **Dark theme** - SaaS production quality
- ✅ **TypeScript** - Full type safety
- ✅ **Design tokens** - Consistent styling
- ✅ **Animations** - Framer Motion for smooth transitions
- ✅ **Accessibility** - ARIA labels, keyboard navigation
- ✅ **Responsive** - Mobile-first design
- ✅ **Micro-interactions** - Hover/active states
- ✅ **Loading states** - Proper feedback
- ✅ **WebSocket streaming** - Real-time token streaming
- ✅ **Step tracking** - Visible agent workflow
- ✅ **Code highlighting** - Syntax highlighting for code blocks

---

## 🧪 Testing

```bash
npm run test
npm run test:coverage
```

---

## 📝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

---

## 📄 License

MIT License

---

## 🤝 Credits

Built with:
- **Next.js** 16
- **React** 18
- **Tailwind CSS** 4
- **TypeScript** 5.x
- **Framer Motion** for animations
- **Zustand** for state management

---

**Dernière mise à jour**: 2026-04-29