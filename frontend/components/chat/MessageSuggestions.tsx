// MessageSuggestions.tsx
// Role: Contextual action buttons below AI responses — grouped by priority

'use client'

import { useState } from 'react'
import { Wand2, FileCode, Zap, Shield, Package, ChevronDown, ChevronUp } from 'lucide-react'
import { useI18n } from '@/lib/i18n'

interface MessageSuggestionsProps {
  onSuggestion: (prompt: string) => void
}

export function MessageSuggestions({ onSuggestion }: MessageSuggestionsProps) {
  const { t } = useI18n()
  const [showAll, setShowAll] = useState(false)
  
  const primaryActions = [
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
  ]

  const advancedTools = [
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
      {/* Primary actions */}
      {primaryActions.map((s) => (
        <button
          key={s.key}
          onClick={() => onSuggestion(s.prompt)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-violet-900/30 hover:bg-violet-800/40 border border-violet-700/40 hover:border-violet-600/60 rounded-lg text-violet-300 hover:text-violet-200 transition-colors font-medium"
        >
          <s.icon className="w-3.5 h-3.5" />
          {t.suggestions[s.key]}
        </button>
      ))}

      {/* Advanced tools toggle */}
      <button
        onClick={() => setShowAll(!showAll)}
        className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600 rounded-lg text-slate-500 hover:text-slate-300 transition-colors"
      >
        {showAll ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {showAll ? 'Less' : 'More'}
      </button>

      {/* Advanced tools (collapsible) */}
      {showAll && advancedTools.map((s) => (
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
