// MessageSuggestions.tsx
// Role: Contextual action buttons below AI responses

'use client'

import { Wand2, FileCode, Zap, Shield, Package } from 'lucide-react'
import { useI18n } from '@/lib/i18n'

interface MessageSuggestionsProps {
  onSuggestion: (prompt: string) => void
}

export function MessageSuggestions({ onSuggestion }: MessageSuggestionsProps) {
  const { t } = useI18n()
  
  const suggestionPresets = [
    { icon: Wand2, key: 'improveCode' as const, prompt: 'Improve this code: ' },
    { icon: FileCode, key: 'addTests' as const, prompt: 'Add unit tests for: ' },
    { icon: Zap, key: 'fastapiVersion' as const, prompt: 'Create a FastAPI endpoint for: ' },
    { icon: Shield, key: 'makeRobust' as const, prompt: 'Make this more robust with error handling: ' },
    { icon: Package, key: 'convertPackage' as const, prompt: 'Convert this into a Python package: ' },
  ]

  return (
    <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-800">
      {suggestionPresets.map((s) => (
        <button
          key={s.key}
          onClick={() => onSuggestion(s.prompt)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600 rounded-lg text-slate-400 hover:text-slate-300 transition-colors"
        >
          <s.icon className="w-3.5 h-3.5" />
          {t.suggestions[s.key]}
        </button>
      ))}
    </div>
  )
}