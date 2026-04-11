import type { Metadata } from 'next'
import './globals.css'

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
    <html lang="en" className="dark">
      <body className="antialiased bg-black text-white">{children}</body>
    </html>
  )
}