'use client'

import React from 'react'

// ButtonComponent interface - variants: primary|secondary|ghost|danger
export type ButtonComponentVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
// Base button classes shared across all variants
// Transition + disable state, no padding/margin (handled per variant)
// Variant classes include: background, hover, text color, active state
// Accessibility: aria-disabled via disabled prop mapping

export interface ButtonComponentProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonComponentVariant
  size?: 'xs' | 'sm' | 'md' | 'lg'
  fullWidth?: boolean
  isLoading?: boolean
  icon?: React.ReactNode
}

// Button base styles
// padding varies per size, rounded-lg consistent, transition-all enabled
// font-medium for semibold weights, text-sm base size
// focus-visible outline for keyboard navigation (Tailwind handles visible focus ring)
const buttonBase = {
  base: 'inline-flex items-center justify-center gap-2 font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 disabled:opacity-50 disabled:cursor-not-allowed',
  sizes: {
    xs: 'px-2 py-1 text-xs rounded-md',
    sm: 'px-3 py-1.5 text-xs rounded-lg',
    md: 'px-4 py-2 text-sm rounded-lg',
    lg: 'px-6 py-3 text-sm rounded-xl',
  },
  variants: {
    primary: 'bg-violet-600 hover:bg-violet-700 active:bg-violet-800 text-white shadow-sm hover:shadow-md hover:-translate-y-0.5',
    secondary: 'bg-slate-800 hover:bg-slate-700 active:bg-slate-900 text-white hover:shadow-md hover:-translate-y-0.5',
    ghost: 'bg-transparent hover:bg-slate-800/50 text-slate-300 hover:bg-slate-800 active:bg-slate-900',
    danger: 'bg-red-600 hover:bg-red-700 active:bg-red-800 text-white shadow-sm hover:shadow-md hover:-translate-y-0.5',
  },
}

// Loading state spinner
const spinner = <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />

// MessageBubble description: chat message component with user/assistant distinction
// User messages are right-aligned with accent background
// Assistant messages are left-aligned with neutral background
// Message content supports markdown (assumes ReactMarkdown or similar is mounted)
// Max-width constraint for long messages, proper line breaks
// Avatar circle for assistant messages, hidden for user messages

export interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: React.ReactNode
  isLoading?: boolean
  onReply?: (id: string) => void
}

export function MessageBubble({
  role,
  content,
  isLoading = false,
}: MessageBubbleProps) {
  // User messages are right-aligned, assistant are left-aligned
  // Avatar uses emerald for assistant, white circle for user placeholder
  const isUser = role === 'user'

  return (
    <div className={`flex gap-3 w-full ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs">
          🤖
        </div>
      )}

      <div
        className={`relative max-w-[85%] px-4 py-3 rounded-2xl break-words ${
          isUser
            ? 'bg-violet-600 text-white rounded-br-md'
            : 'bg-slate-800 text-slate-200 rounded-bl-md'
        }`}
      >
        {/* Loading indicator for assistant messages */}
        {isLoading && !isUser && (
          <div className="flex gap-1.5 mt-2">
            <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        )}

        {/* Message content */}
        <div className={isLoading ? 'space-y-1' : 'whitespace-pre-wrap break-words'}>
          {content}
        </div>
      </div>
    </div>
  )
}
// TypingIndicator description: 3 animated dots showing AI is "thinking"
// Uses framer-motion for smooth transitions
// Dots bounce with staggered delays
// Fixed colors matching theme slate-400

export function TypingIndicator() {
  // Three dots with staggered animation delays for realistic typing effect
  // Fixed size and spacing, rounded-full for perfect circles
  return (
    <div className="flex gap-1.5 px-4 py-2 bg-slate-800/50 rounded-full">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
          style={{
            animationDelay: `${i * 150}ms`,
            animationDuration: '1s',
            display: 'inline-block',
          }}
        />
      ))}
    </div>
  )
}

// StepItem - uses shared AgentStep type from types.ts
import type { AgentStep } from '@/lib/types'

interface StepItemProps {
  step: AgentStep
}

// Status config - consistent with agent/StepItem.tsx
const statusConfig: Record<AgentStep['status'], { icon: string; badge: string; color: string }> = {
  done: { icon: '✓', badge: 'done', color: 'text-emerald-400' },
  active: { icon: '→', badge: 'active', color: 'text-violet-400' },
  pending: { icon: '-', badge: 'pending', color: 'text-slate-500' },
  error: { icon: '!', badge: 'error', color: 'text-red-400' },
}

export function StepItem({ step }: StepItemProps) {
  const config = statusConfig[step.status] || statusConfig.pending
  
  return (
    <div className="flex items-start gap-3 py-1.5 -ml-3 pl-3 border-l-2 border-slate-800/50">
      {/* Status icon */}
      <span className={`flex-shrink-0 text-base ${config.color}`}>{config.icon}</span>

      {/* Title with optional status indicator */}
      <div className="flex-1 min-w-0">
        <span
          className={`${
            step.status === 'active' ? 'text-white font-medium' : step.status === 'error' ? 'text-red-300' : 'text-slate-400'
          } truncate`}
        >
          {step.title}
          {(step.status === 'active' || step.status === 'error') && (
            <span className={`ml-1 text-xs ${config.color}`}>({config.badge})</span>
          )}
        </span>

        {/* Optional detail */}
        {step.detail && (
          <span className="inline-block w-2 ml-2 mt-1 text-slate-500 text-xs truncate">
            • {step.detail}
          </span>
        )}
      </div>

      {/* Status badge */}
      <span
        className={`text-xs px-2 py-0.5 rounded-full ${
          step.status === 'done' ? 'bg-emerald-900/30 text-emerald-400' 
          : step.status === 'active' ? 'bg-violet-900/30 text-violet-400'
          : step.status === 'error' ? 'bg-red-900/30 text-red-400'
          : 'bg-slate-800 text-slate-500'
        }`}
      >
        {config.badge}
      </span>
    </div>
  )
}
