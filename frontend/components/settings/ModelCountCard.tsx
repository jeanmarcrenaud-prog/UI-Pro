// ModelCountCard.tsx
'use client'

import { useModelDiscovery } from './hooks/useModelDiscovery'

export function ModelCountCard() {
  const { models } = useModelDiscovery()
  const modelCount = models.length

  return (
    <section className="bg-[#0f172a] rounded-xl p-4 border border-slate-700/50">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        📊 Modèles
      </h3>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold text-white">{modelCount}</span>
        <span className="text-xs text-slate-500">disponibles</span>
      </div>
    </section>
  )
}