// layout.tsx (app/)
// Role: Root layout component - sets up Next.js app router metadata, imports global styles,
// configures dark mode, and wraps app with error boundary for crash recovery

import type { Metadata } from 'next'
import './globals.css'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { DebugPanel } from '@/components/DebugPanel'
import { ThemeProvider } from '@/components/ThemeProvider'

export const metadata: Metadata = {
  title: 'UI-Pro - AI Agent Orchestration',
  description: 'AI Agent Orchestration System',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className="antialiased bg-[var(--bg-primary)] text-[var(--text-primary)] transition-colors duration-200">
        <ErrorBoundary>
          <ThemeProvider>
            {children}
          </ThemeProvider>
        </ErrorBoundary>
        <DebugPanel />
      </body>
    </html>
  )
}