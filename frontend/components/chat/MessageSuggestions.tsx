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
    {
      icon: Wand2,
      key: 'improveCode' as const,
      prompt: `Review and improve this code for performance, readability, and correctness. Preserve the public API, no new dependencies, focused diff. Output: diagnosis + improved code + summary.

{code}`,
    },
    {
      icon: FileCode,
      key: 'addTests' as const,
      prompt: `Write pytest tests for this code. One test per behavior, parametrize for cases, fixtures for shared setup. Cover: happy path, edge cases, error cases. Aim for 80%+ coverage.

{code}`,
    },
    {
      icon: Zap,
      key: 'fastapiVersion' as const,
      prompt: `Convert this into a FastAPI endpoint with Pydantic v2 models, proper status codes (200/201/204/404/422), and OpenAPI docstrings. Output a complete runnable file.

{code}`,
    },
    {
      icon: Shield,
      key: 'makeRobust' as const,
      prompt: `Add proper error handling and structured logging to this code. Catch specific exceptions (never bare except:), preserve exception chains with "raise ... from e", use the logging module (not print) with lazy formatting.

{code}`,
    },
    {
      icon: Package,
      key: 'convertPackage' as const,
      prompt: `Convert this into a modern Python package (src/ layout, pyproject.toml with PEP 621). Include __init__.py, py.typed marker, and a basic test file. Specify requires-python, dependencies, and dev extras.

{code}`,
    },
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