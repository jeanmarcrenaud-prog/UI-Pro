// ThemeProvider.tsx
// Role: Syncs theme from uiStore to <html> className on mount and changes

'use client'

import { useEffect } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useUIStore((s) => s.theme)

  useEffect(() => {
    document.documentElement.className = theme
  }, [theme])

  return <>{children}</>
}
