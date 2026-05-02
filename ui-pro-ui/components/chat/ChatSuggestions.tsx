// ChatSuggestions.tsx
// Role: Contextual suggestions based on current message/code

'use client'

import { Sparkles, Zap, Shield, TestTube, FileCode, LogOut } from 'lucide-react'

interface ChatSuggestionsProps {
  onSelect: (suggestion: string) => void
  context?: string  // Last assistant message or code context
}

const SUGGESTIONS = [
  { icon: Zap, label: 'Improve script', prompt: 'Improve this script with better performance' },
  { icon: LogOut, label: 'Add logging', prompt: 'Add logging and error handling' },
  { icon: FileCode, label: 'Convert to API', prompt: 'Convert this to a FastAPI endpoint' },
  { icon: TestTube, label: 'Add tests', prompt: 'Add unit tests for this code' },
  { icon: Shield, label: 'Add types', prompt: 'Add TypeScript types' },
]

// Suggestions adaptés au contexte (futur: IA-based)
function getContextualSuggestions(context?: string): string[] {
  // Pour l'instant, retourne tous les prompts
  // Plus tard: analyser le contexte pour filtrer
  return SUGGESTIONS.map(s => s.prompt)
}

export function ChatSuggestions({ onSelect, context }: ChatSuggestionsProps) {
  const suggestions = getContextualSuggestions(context)

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2">
      <div className="text-xs text-slate-500 mr-2 flex items-center">
        <Sparkles className="w-3 h-3 mr-1" />
        Suggestions:
      </div>
      {SUGGESTIONS.map((item, i) => (
        <button
          key={i}
          onClick={() => onSelect(item.prompt)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/50 hover:border-slate-600"
        >
          <item.icon className="w-3 h-3" />
          {item.label}
        </button>
      ))}
    </div>
  )
}