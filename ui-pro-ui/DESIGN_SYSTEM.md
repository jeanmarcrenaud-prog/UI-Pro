# UI-Pro Design System Documentation

## 🎨 Overview

This is the official design system for UI-Pro - a SaaS-level, ChatGPT-like AI chat interface built with Next.js 14, Tailwind CSS 3.8, and TypeScript.

---

## 📁 File Structure

```
ui-pro-ui/
├── styles/
│   └── tokens.ts           # Design system tokens (colors, spacing, typography)
│
├── components/
│   ├── ui/                # Atomic UI components
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Input.tsx
│   │   ├── Textarea.tsx
│   │   ├── Select.tsx
│   │   ├── Badge.tsx
│   │   └── index.ts
│   │
│   ├── chat/              # Chat-specific components
│   │   ├── MessageBubble.tsx
│   │   ├── TypingIndicator.tsx
│   │   ├── ChatMessages.tsx
│   │   ├── AgentSteps.tsx
│   │   └── index.ts
│   │
│   └── agent/             # Agent workflow components
│       ├── StepItem.tsx
│       ├── AgentSteps.tsx
│       └── index.ts
│
├── tailwind.config.js     # Tailwind extended theme
└── app/
    ├── globals.css        # Global styles with CSS variables
    └── layout.tsx         # Root layout
```

---

## 🎨 Design Tokens

### Colors

```typescript
// Dark theme base (SaaS production quality)
bg: {
  primary: '#020617',     // Deep dark background
  secondary: '#0f172a',   // Panels and content areas
  tertiary: '#020617cc',  // Overlays
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
  secondary: '#cbd5f5',
  muted: '#64748b',
  disabled: '#475569',
}

accent: {
  primary: '#7c3aed',      // Violet (brand)
  hover: '#6d28d9',
  soft: '#a78bfa33',
}

// Status colors
success: '#22c55e'
warning: '#eab308'
error: '#ef4444'
```

### Spacing

```
xs: 4px
sm: 8px
md: 12px
lg: 16px
xl: 24px
xxl: 32px
```

### Typography

```
xs: 12px
sm: 13px
md: 14px
lg: 16px
xl: 18px
xxl: 20px

font: 'Inter, sans-serif'
```

---

## 🧩 Components

### Button

```tsx
import { Button } from '@/components/ui'

<Button variant="primary">Primary</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="danger">Danger</Button>

// With loading state
<Button isLoading={true}>Loading...</Button>

// With icon
<Button icon={<span>➤</span>}>Submit</Button>
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

### Message Bubble

```tsx
import { MessageBubble } from '@/components/chat'

<MessageBubble role="user" content="Hello!" />
<MessageBubble 
  role="assistant" 
  content={<AgentSteps />}
/>
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
- **Next.js** 14
- **React** 18
- **Tailwind CSS** 3.8
- **TypeScript** 5.x
- **Framer Motion** for animations
- **Zustand** for state management
