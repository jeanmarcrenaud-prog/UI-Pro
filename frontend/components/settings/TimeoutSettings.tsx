// TimeoutSettings.tsx
'use client'

import { useTimeouts } from './hooks/useTimeouts'
import { useI18n } from '@/lib/i18n'

export function TimeoutSettings() {
  const { t } = useI18n()
  const { llmTimeout, executorTimeout, setLlmTimeout, setExecutorTimeout, isSaving, message, saveTimeouts } = useTimeouts()

  return (
    <section className="glass-panel rounded-xl p-4 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        ⏱️ {t.settings.timeouts}
      </h3>
      <div className="space-y-3">
        {/* LLM Timeout */}
        <div>
          <label className="text-[10px] text-slate-500 block mb-1">{t.settings.llmTimeout}</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={30}
              max={1800}
              value={llmTimeout}
              onChange={(e) => setLlmTimeout(Number(e.target.value))}
              className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-violet-500 transition-colors"
            />
            <span className="text-xs text-slate-400">{t.settings.seconds}</span>
          </div>
          <p className="text-[9px] text-slate-600 mt-0.5">{t.settings.llmTimeoutHelp}</p>
        </div>
        {/* Executor Timeout */}
        <div>
          <label className="text-[10px] text-slate-500 block mb-1">{t.settings.executorTimeout}</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={5}
              max={600}
              value={executorTimeout}
              onChange={(e) => setExecutorTimeout(Number(e.target.value))}
              className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-violet-500 transition-colors"
            />
            <span className="text-xs text-slate-400">{t.settings.seconds}</span>
          </div>
          <p className="text-[9px] text-slate-600 mt-0.5">{t.settings.executorTimeoutHelp}</p>
        </div>
      </div>
      <button
        onClick={() => saveTimeouts(t)}
        disabled={isSaving}
        className="mt-3 w-full px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:bg-violet-800/70 disabled:cursor-wait text-white text-xs font-medium rounded-lg transition-all flex items-center justify-center gap-1.5"
      >
        {isSaving ? '...' : '💾'}
        {isSaving ? 'Saving...' : 'Save'}
      </button>
      {message && (
        <p className={`mt-2 text-[10px] text-center rounded px-2 py-1 ${message.type === 'success' ? 'bg-emerald-900/50 text-emerald-400' : 'bg-red-900/50 text-red-400'}`}>
          {message.text}
        </p>
      )}
    </section>
  )
}