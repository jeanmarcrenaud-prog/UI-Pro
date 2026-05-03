// ChatSuggestions.tsx
// Role: Contextual suggestions based on current message/code

'use client'

import { Sparkles, Zap, Shield, TestTube, FileCode, LogOut } from 'lucide-react'

interface ChatSuggestionsProps {
  onSelect: (suggestion: string) => void
  lastCode?: string  // Code from last assistant message
}

const SUGGESTIONS = [
  { icon: Zap, label: 'Improve script', prompt: (code: string) => `Improve this script:\n${code}\n\nImprove with better performance and best practices.` },
  { icon: LogOut, label: 'Add logging', prompt: (code: string) => `Add logging and error handling:\n${code}\n\nAdd proper logging and exception handling.` },
  { icon: FileCode, label: 'Convert to API', prompt: (code: string) => `Convert to FastAPI:\n${code}\n\nConvert this to a FastAPI endpoint with proper routing.` },
  { icon: TestTube, label: 'Add tests', prompt: (code: string) => `Add unit tests:\n${code}\n\nWrite pytest unit tests for this code.` },
  { icon: Shield, label: 'Add types', prompt: (code: string) => `Add TypeScript:\n${code}\n\nAdd proper TypeScript types and interfaces.` },
]

// Get prompts with code injected
function getContextualPrompts(code?: string): string[] {
  if (!code) {
    // Generic prompts when no code available
    return [
      "Improve this script with better performance",
      "Add logging and error handling",
      "Convert this to a FastAPI endpoint",
      "Add unit tests for this code",
      "Add proper TypeScript types",
    ]
  }
  return SUGGESTIONS.map(s => s.prompt(code))
}

export function ChatSuggestions({ onSelect, lastCode }: ChatSuggestionsProps) {
  const prompts = getContextualPrompts(lastCode)

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2">
      <div className="text-xs text-slate-500 mr-2 flex items-center">
        <Sparkles className="w-3 h-3 mr-1" />
        Suggestions:
      </div>
      {SUGGESTIONS.map((item, i) => (
        <button
          key={i}
          onClick={() => onSelect(prompts[i])}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/50 hover:border-slate-600"
        >
          <item.icon className="w-3 h-3" />
          {item.label}
        </button>
      ))}
    </div>
  )
}