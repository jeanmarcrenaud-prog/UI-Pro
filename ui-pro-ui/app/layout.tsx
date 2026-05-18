// layout.tsx (app/)
// Role: Root layout component - sets up Next.js app router metadata, imports global styles,
// configures dark mode, and wraps app with error boundary for crash recovery

import type { Metadata } from 'next'
import './globals.css'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { DebugPanel } from '@/components/DebugPanel'

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
    <html lang="fr" className="dark">
      <body className="antialiased bg-black text-white">
        <ErrorBoundary>
          {children}
        </ErrorBoundary>
        <DebugPanel />
      </body>
    </html>
  )
}