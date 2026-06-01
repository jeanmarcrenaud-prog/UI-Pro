// SettingsView.tsx
'use client'

import { motion } from 'framer-motion'
import { useI18n } from '@/lib/i18n'

import { LanguageSelector } from './settings/LanguageSelector'
import { AboutCard } from './settings/AboutCard'
import { TimeoutSettings } from './settings/TimeoutSettings'
import { LogLevelSettings } from './settings/LogLevelSettings'
import { ModelCountCard } from './settings/ModelCountCard'
import { ModelSelector } from './settings/ModelSelector'
import { BackendStatusGrid } from './settings/BackendStatusGrid'
import { ThemeSelector } from './settings/ThemeSelector'
import { SystemStats } from './SystemStats'

export function SettingsView() {
  const { t } = useI18n()

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.23, 1, 0.32, 1] }}
      className="flex-1 p-6 sm:p-8 overflow-y-auto"
    >
      {/* Header - Compact */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">
          {t.settings.title}
        </h2>
        <p className="text-sm text-[var(--text-muted)] mt-1.5">
          {t.settings.subtitle}
        </p>
      </div>

      {/* Dashboard Grid - 3 columns on large screens */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 theme-transition">
        
        {/* Language - Compact Card */}
        <LanguageSelector />

        {/* Theme - Compact Card */}
        <ThemeSelector />

        {/* About - Compact Card */}
        <AboutCard />

        {/* Timeout Settings - Compact Card */}
        <TimeoutSettings />

        {/* Log Level Settings - Compact Card */}
        <LogLevelSettings />

        {/* Model Count - Compact Card */}
        <ModelCountCard />

        {/* Models Section - Full Width */}
        <ModelSelector className="md:col-span-2 lg:col-span-3" />

        {/* Backend Connections - Full Width Live Cards */}
        <BackendStatusGrid className="md:col-span-2 lg:col-span-3" />

        {/* System Stats - Full Width */}
        <section className="md:col-span-2 lg:col-span-3 pt-2">
          <SystemStats />
        </section>
      </div>
    </motion.div>
  )
}