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
import { SystemStats } from './SystemStats'

export function SettingsView() {
  const { t } = useI18n()

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="flex-1 p-4 sm:p-6 overflow-y-auto"
    >
      {/* Header - Compact */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white tracking-tight">
          {t.settings.title}
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          {t.settings.subtitle}
        </p>
      </div>

      {/* Dashboard Grid - 3 columns on large screens */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        
        {/* Language - Compact Card */}
        <LanguageSelector />

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