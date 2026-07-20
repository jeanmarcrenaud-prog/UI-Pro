// AboutCard.tsx
'use client'

import { useI18n } from '@/lib/i18n'

export function AboutCard() {
  const { t } = useI18n()
  return (
    <section className="glass-panel rounded-xl p-4 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        {t.settings.about}
      </h3>
      <a 
        href="https://github.com/jeanmarcrenaud-prog/UI-Pro" 
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-between p-2 -mx-2 rounded-lg hover:bg-slate-800/50 transition-colors group"
      >
        <div>
          <p className="text-sm font-semibold text-white group-hover:text-violet-300 transition-colors">UI-Pro</p>
          <p className="text-[11px] text-slate-500 mt-0.5">{t.settings.aboutVersion}</p>
        </div>
        <span className="text-emerald-400 text-lg">✓</span>
      </a>
    </section>
  )
}