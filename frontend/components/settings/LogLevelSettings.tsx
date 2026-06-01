// LogLevelSettings.tsx
'use client'

import { useLogLevel } from './hooks/useLogLevel'
import { useI18n } from '@/lib/i18n'

const LEVEL_DESCRIPTIONS: Record<string, string> = {
  DEBUG: 'Detailed debugging information',
  INFO: 'General informational messages',
  WARNING: 'Warning messages for issues',
  ERROR: 'Error messages only',
  CRITICAL: 'Critical errors only',
}

export function LogLevelSettings() {
  const { t } = useI18n()
  const { currentLevel, availableLevels, isSaving, message, setLevel, saveLevel } = useLogLevel()

  return (
    <section className="glass-panel rounded-xl p-4 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        📋 Log Level
      </h3>
      <div className="space-y-3">
        <div>
          <label className="text-[10px] text-slate-500 block mb-2">Current Level</label>
          <select
            value={currentLevel}
            onChange={(e) => setLevel(e.target.value)}
            className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition-colors"
          >
            {availableLevels.map(level => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
          <p className="text-[9px] text-slate-600 mt-1">
            {LEVEL_DESCRIPTIONS[currentLevel]}
          </p>
        </div>
      </div>
      <button
        onClick={() => saveLevel(t)}
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