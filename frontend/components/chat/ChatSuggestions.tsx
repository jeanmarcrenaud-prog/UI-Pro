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
    { icon: Zap, key: 'improve' as const },
    { icon: LogOut, key: 'logging' as const },
    { icon: FileCode, key: 'api' as const },
    { icon: TestTube, key: 'tests' as const },
    { icon: Shield, key: 'types' as const },
  ]

  // Generate prompts with i18n template
  const getPrompt = (key: string, code: string) => {
    const templateKey = key + 'Prompt' as keyof typeof t.suggestions
    const template = t.suggestions[templateKey] as string
    return template.replace('{code}', code || '')
  }

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2">
      <div className="text-xs text-slate-500 mr-2 flex items-center">
        <Sparkles className="w-3 h-3 mr-1" />
        {t.suggestions.title}:
      </div>
      {SUGGESTIONS.map((item) => (
        <button
          key={item.key}
          onClick={() => onSelect(getPrompt(item.key, lastCode || ''))}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/50 hover:border-slate-600"
        >
          <item.icon className="w-3 h-3" />
          {t.suggestions[item.key]}
        </button>
      ))}
    </div>
  )
}