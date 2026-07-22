// lib/i18n.ts — React hook for i18n
'use client'

import { useState, useEffect } from 'react'
import type { Locale, Translations } from './i18n-types'
import { translations, defaultLocale } from './i18n-data'

export type { Locale, Translations } from './i18n-types'

export function useI18n() {
  const [locale, setLocaleState] = useState<Locale>('en')

  // Load locale from localStorage on mount
  useEffect(() => {
    try {
      const savedLocale = localStorage.getItem('locale') as Locale
      if (savedLocale === 'en' || savedLocale === 'fr') {
        setLocaleState(savedLocale)
      }
    } catch {
      // ignore
    }
  }, [])

  // Get current translations based on locale
  const t = translations[locale]

  const changeLocale = (newLocale: Locale) => {
    setLocaleState(newLocale)
    try {
      localStorage.setItem('locale', newLocale)
    } catch {
      // ignore
    }
  }

  return {
    t,
    locale,
    setLocale: changeLocale,
  }
}

// Alias for getTranslations
export function getTranslations(loc: Locale): Translations {
  return translations[loc]
}

export { defaultLocale }
export { STEP_STATUS_LABELS } from './i18n-data'
