// LanguageSelector.tsx
'use client'

import { useI18n, type Locale } from '@/lib/i18n'

export function LanguageSelector() {
  const { t, locale, setLocale } = useI18n()

  const handleChange = (newLocale: Locale) => {
    setLocale(newLocale)
  }

  return (
    <section className="glass-panel rounded-xl p-4 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        🌐 {t.settings.language}
      </h3>
      <select
        value={locale}
        onChange={(e) => handleChange(e.target.value as Locale)}
        className="w-full bg-[#172033] border border-slate-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500 transition-colors"
      >
        <option value="fr">🇫🇷 Français</option>
        <option value="en">🇬🇧 English</option>
      </select>
    </section>
  )
}