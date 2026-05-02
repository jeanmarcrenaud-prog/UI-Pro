// MessageSuggestions.tsx
// Role: Contextual action buttons below AI responses

'use client'

import { Wand2, FileCode, Zap, Shield, Package } from 'lucide-react'

interface MessageSuggestionsProps {
  onSuggestion: (prompt: string) => void
}

// Contextual suggestions that adapt based on content
const suggestionPresets = [
  { label: 'Improve code', icon: Wand2, prompt: 'Improve this code: ' },
  { label: 'Add tests', icon: FileCode, prompt: 'Add unit tests for: ' },
  { label: 'FastAPI version', icon: Zap, prompt: 'Create a FastAPI endpoint for: ' },
  { label: 'Make robust', icon: Shield, prompt: 'Make this more robust with error handling: ' },
  { label: 'Convert to package', icon: Package, prompt: 'Convert this into a Python package: ' },
]

export function MessageSuggestions({ onSuggestion }: MessageSuggestionsProps) {
  return (
    <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-slate-800">
      {suggestionPresets.map((s) => (
        <button
          key={s.label}
          onClick={() => onSuggestion(s.prompt)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600 rounded-lg text-slate-400 hover:text-slate-300 transition-colors"
        >
          <s.icon className="w-3.5 h-3.5" />
          {s.label}
        </button>
      ))}
    </div>
  )
}