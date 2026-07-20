// EnableThinkingSettings.tsx
// Toggle for LLM thinking-mode (chain-of-thought) handling. Affects
// models like Qwen3.5+, OpenAI o1/o3, DeepSeek-R1 that spend most
// of their `max_tokens` budget on internal reasoning before any
// visible response. When OFF, the LLM mixin injects
// `chat_template_kwargs={"enable_thinking": false}` so the model
// jumps straight to the answer. When ON, the model is allowed to
// reason internally (useful for o1-style workflows where the
// reasoning IS the deliverable).

'use client'

import { useEnableThinking } from './hooks/useEnableThinking'
import { useI18n } from '@/lib/i18n'

export function EnableThinkingSettings() {
  const { t } = useI18n()
  const { enabled, isLoading, isSaving, message, toggle } = useEnableThinking()
  return (
    <section className="glass-panel rounded-xl p-4 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        {t.settings.thinkingMode}
      </h3>

      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-xs text-slate-300 leading-relaxed">
            {t.settings.thinkingModeDesc}
          </p>
          <p className="text-[10px] text-slate-500 mt-1">
            {enabled
              ? t.settings.thinkingModeEnabledHelp
              : t.settings.thinkingModeDisabledHelp}
          </p>
        </div>

        <button
          onClick={toggle}
          disabled={isLoading}
          role="switch"
          aria-checked={enabled}
          aria-label={t.settings.thinkingToggleAria}
          className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-violet-500/50 ${
            enabled ? 'bg-violet-600' : 'bg-slate-600'
          } ${isLoading ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-lg transition-transform ${
              enabled ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {/* Status line */}
      <div className="mt-2 flex items-center gap-2 min-h-[16px]">
        {isSaving && (
          <span className="text-[10px] text-slate-500">⏳ {t.settings.saving}</span>
        )}
        {message && (
          <p
            className={`text-[10px] ${
              message.type === 'success' ? 'text-emerald-400' : 'text-red-400'
            }`}
          >
            {message.type === 'success' ? '✅' : '⚠️'} {message.text}
          </p>
        )}
      </div>
    </section>
  )
}
