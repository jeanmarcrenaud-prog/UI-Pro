// ChatSuggestions.tsx
// Role: Contextual suggestions based on current message/code

'use client'

import { Sparkles, Zap, Shield, TestTube, FileCode, LogOut } from 'lucide-react'
import { useI18n } from '@/lib/i18n'

interface ChatSuggestionsProps {
  onSelect: (suggestion: string) => void
  lastCode?: string  // Code from last assistant message
}

export function ChatSuggestions({ onSelect, lastCode }: ChatSuggestionsProps) {
  const { t } = useI18n()
  
  const SUGGESTIONS = [
    { icon: Zap, key: 'improve' as const, prompt: (code: string) => `Improve this script:\n${code}\n\nImprove with better performance and best practices.` },
    { icon: LogOut, key: 'logging' as const, prompt: (code: string) => `Add logging and error handling:\n${code}\n\nAdd proper logging and exception handling.` },
    { icon: FileCode, key: 'api' as const, prompt: (code: string) => `Convert to FastAPI:\n${code}\n\nConvert this to a FastAPI endpoint with proper routing.` },
    { icon: TestTube, key: 'tests' as const, prompt: (code: string) => `Add unit tests:\n${code}\n\nWrite pytest unit tests for this code.` },
    { icon: Shield, key: 'types' as const, prompt: (code: string) => `Add TypeScript:\n${code}\n\nAdd proper TypeScript types and interfaces.` },
  ]

  // Get prompts with code injected
  const prompts = SUGGESTIONS.map(s => s.prompt(lastCode || ''))

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2">
      <div className="text-xs text-slate-500 mr-2 flex items-center">
        <Sparkles className="w-3 h-3 mr-1" />
        {t.suggestions.title}:
      </div>
      {SUGGESTIONS.map((item, i) => (
        <button
          key={i}
          onClick={() => onSelect(prompts[i])}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/50 hover:border-slate-600"
        >
          <item.icon className="w-3 h-3" />
          {t.suggestions[item.key]}
        </button>
      ))}
    </div>
  )
}