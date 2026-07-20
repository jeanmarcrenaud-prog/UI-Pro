// settings/ThemeSelector.tsx
'use client'

import { useUIStore } from '@/lib/stores/uiStore'
import { useI18n } from '@/lib/i18n'
import { Monitor, Sun, Moon, Sparkles, Palette } from 'lucide-react'

const THEMES = [
  { id: 'dark' as const, icon: Moon },
  { id: 'light' as const, icon: Sun },
  { id: 'purple-rain' as const, icon: Sparkles },
  { id: 'pro' as const, icon: Palette },
]

export function ThemeSelector() {
  const { theme, setTheme } = useUIStore()
  const { t } = useI18n()

  const themeLabel = (id: string) => {
    switch (id) {
      case 'dark': return t.settings.themeLabelDark
      case 'light': return t.settings.themeLabelLight
      case 'purple-rain': return t.settings.themeLabelPurpleRain
      case 'pro': return t.settings.themeLabelPro
      default: return id
    }
  }

  const themeDesc = (id: string) => {
    switch (id) {
      case 'dark': return t.settings.themeDescDark
      case 'light': return t.settings.themeDescLight
      case 'purple-rain': return t.settings.themeDescPurpleRain
      case 'pro': return t.settings.themeDescPro
      default: return ''
    }
  }

  return (
    <section className="glass-panel rounded-xl p-4 transition-all duration-200">
      <h3 className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] mb-3 flex items-center gap-2">
        <Monitor className="w-3.5 h-3.5" />
        {t.settings.themeSelector}
      </h3>

      <div className="grid grid-cols-3 gap-2">
        {THEMES.map((item) => {
          const Icon = item.icon
          const isActive = theme === item.id
          return (
            <button
              key={item.id}
              onClick={() => setTheme(item.id)}
              className={`
                flex flex-col items-center gap-1.5 p-3 rounded-xl text-xs transition-all duration-200
                ${isActive
                  ? 'bg-[var(--accent)] text-white shadow-lg shadow-[var(--accent)]/20 scale-105'
                  : 'bg-[var(--surface-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--border-default)]'
                }
              `}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-white' : ''}`} />
              <span className="font-medium">{themeLabel(item.id)}</span>
              {isActive && (
                <span className="text-[10px] opacity-70">{themeDesc(item.id)}</span>
              )}
            </button>
          )
        })}
      </div>
    </section>
  )
}
