// HermesSettings.tsx
'use client'

import { useHermesSettings } from './hooks/useHermesSettings'
import { useI18n } from '@/lib/i18n'

export function HermesSettings() {
  const { t } = useI18n()
  const {
    baseUrl,
    model,
    setBaseUrl,
    setModel,
    isSaving,
    message,
    saveHermesConfig,
  } = useHermesSettings()

  return (
    <section className="glass-panel rounded-xl p-4 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        🧠 {t.settings.hermesSettings}
      </h3>
      <div className="space-y-3">
        {/* LLM Base URL */}
        <div>
          <label className="text-[10px] text-slate-500 block mb-1">{t.settings.hermesBaseUrl}</label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://localhost:1234/v1"
            className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-violet-500 transition-colors"
          />
          <p className="text-[9px] text-slate-600 mt-0.5">{t.settings.hermesBaseUrlHelp}</p>
        </div>
        {/* LLM Model */}
        <div>
          <label className="text-[10px] text-slate-500 block mb-1">{t.settings.hermesModel}</label>
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="google/gemma-4-12b-qat"
            className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-violet-500 transition-colors"
          />
          <p className="text-[9px] text-slate-600 mt-0.5">{t.settings.hermesModelHelp}</p>
        </div>
      </div>
      <p className="text-[9px] text-amber-500/80 mt-2">{t.settings.hermesRestartNote}</p>
      <div className="mt-3">
        <button
          onClick={() => saveHermesConfig(t)}
          disabled={isSaving}
          className="w-full px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:bg-violet-800/70 disabled:cursor-wait text-white text-xs font-medium rounded-lg transition-all flex items-center justify-center gap-1.5"
        >
          {isSaving ? '...' : '💾'}
          {isSaving ? t.settings.saving : t.settings.save}
        </button>
      </div>
      {message && (
        <p className={`mt-2 text-[10px] text-center rounded px-2 py-1 ${message.type === 'success' ? 'bg-emerald-900/50 text-emerald-400' : 'bg-red-900/50 text-red-400'}`}>
          {message.text}
        </p>
      )}
    </section>
  )
}