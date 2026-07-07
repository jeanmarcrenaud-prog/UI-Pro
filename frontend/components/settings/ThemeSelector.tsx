// settings/ThemeSelector.tsx
'use client'

import { useUIStore } from '@/lib/stores/uiStore'
import { useI18n } from '@/lib/i18n'
import { Monitor, Sun, Moon, Sparkles, Palette } from 'lucide-react'

const THEMES = [
  { id: 'dark' as const, label: 'Sombre', icon: Moon, desc: 'Dark mode classique' },
  { id: 'light' as const, label: 'Clair', icon: Sun, desc: 'Mode jour epure' },
  { id: 'purple-rain' as const, label: 'Purple Rain', icon: Sparkles, desc: 'Theme premium violet' },
  { id: 'pro' as const, label: 'Pro', icon: Palette, desc: 'Cursor/Windsurf style cyan' },
]

export function ThemeSelector() {
  const { theme, setTheme } = useUIStore()
  const { t } = useI18n()

  return (
    <section className="glass-panel rounded-xl p-4 transition-all duration-200">
      <h3 className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-3 flex items-center gap-2">
        <Monitor className="w-3.5 h-3.5" />
        Theme
      </h3>

      <div className="grid grid-cols-3 gap-2">
        {THEMES.map((t) => {
          const Icon = t.icon
          const isActive = theme === t.id
          return (
            <button
              key={t.id}
              onClick={() => setTheme(t.id)}
              className={`
                flex flex-col items-center gap-1.5 p-3 rounded-xl text-xs transition-all duration-200
                ${isActive
                  ? 'bg-[var(--accent)] text-white shadow-lg shadow-[var(--accent)]/20 scale-105'
                  : 'bg-[var(--surface-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--border-default)]'
                }
              `}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-white' : ''}`} />
              <span className="font-medium">{t.label}</span>
              {isActive && (
                <span className="text-[10px] opacity-70">{t.desc}</span>
              )}
            </button>
          )
        })}
      </div>
    </section>
  )
}
