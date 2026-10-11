// HermesConfigModal.tsx
// Role: Read-only Hermes-agent config report + suggested fix (applies via
//       POST /api/hermes/config after user validation). Spec:
//       docs/plans/spec-hermes-config-check.md
'use client'

import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Wrench, Check } from 'lucide-react'

export interface HermesConfigReport {
  configured: boolean
  base_url: string | null
  model: string
  backend: string
  llm_reachable: boolean
  available_models: string[]
  recommended_model: string
  gpu_headroom_ok: boolean
  needs_install: boolean
  message: string
}

export interface HermesConfigChoice {
  base_url?: string
  model?: string
}

interface HermesConfigModalProps {
  isOpen: boolean
  report: HermesConfigReport | null
  onClose: () => void
  /** Called with the validated change; resolves after re-fetching the report. */
  onApply: (choice: HermesConfigChoice) => Promise<void>
  applying?: boolean
  error?: string | null
}

const BACKEND_LABELS: Record<string, string> = {
  lmstudio: 'LM Studio',
  ollama: 'Ollama',
  nvidia: 'NVIDIA API',
  none: 'aucun backend',
}

export function HermesConfigModal({
  isOpen,
  report,
  onClose,
  onApply,
  applying = false,
  error = null,
}: HermesConfigModalProps) {
  // Close on Escape
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])

  const recommended = report?.recommended_model || ''
  const backendLabel = BACKEND_LABELS[report?.backend ?? 'none'] ?? report?.backend ?? ''

  // Resolve the base URL to persist when applying the recommendation: keep the
  // configured one, otherwise fall back to the local default for the backend.
  const suggestedBaseUrl = (): string | undefined => {
    if (report?.base_url) return report.base_url
    if (report?.backend === 'ollama') return 'http://127.0.0.1:11434'
    if (report?.backend === 'lmstudio') return 'http://127.0.0.1:1234/v1'
    return undefined
  }

  const handleApply = () => {
    if (!recommended) return
    void onApply({ base_url: suggestedBaseUrl(), model: recommended })
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="relative w-full max-w-lg mx-4 glass-panel rounded-2xl border border-[var(--border-subtle)] shadow-2xl"
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 12 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-[var(--border-subtle)]">
              <div className="flex items-center gap-2">
                <Wrench className="w-5 h-5 text-violet-400" />
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                  Configuration Hermes
                </h2>
              </div>
              <button
                onClick={onClose}
                className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-secondary)] rounded transition-colors"
                aria-label="Fermer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 space-y-4">
              <p className="text-sm text-[var(--text-muted)]">{report?.message}</p>

              {/* Read-only current config */}
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] block mb-1">
                    Base URL actuelle
                  </label>
                  <input
                    type="text"
                    readOnly
                    value={report?.base_url ?? '—'}
                    className="w-full bg-[var(--surface-secondary)] border border-[var(--border-subtle)] rounded-lg px-3 py-1.5 text-sm text-[var(--text-primary)] outline-none cursor-default"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] block mb-1">
                    Modèle actuel
                  </label>
                  <input
                    type="text"
                    readOnly
                    value={report?.model ?? ''}
                    className="w-full bg-[var(--surface-secondary)] border border-[var(--border-subtle)] rounded-lg px-3 py-1.5 text-sm text-[var(--text-primary)] outline-none cursor-default"
                  />
                </div>
              </div>

              {/* Suggestion */}
              {recommended && (
                <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-3">
                  <p className="text-xs text-[var(--text-muted)] mb-2">Suggestion recommandée</p>
                  <button
                    onClick={handleApply}
                    disabled={applying}
                    className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-sm bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Check className="w-3.5 h-3.5" />
                    Utiliser {recommended}
                    {backendLabel ? ` via ${backendLabel}` : ''}
                  </button>
                </div>
              )}

              {error && (
                <p className="text-xs text-red-400 bg-red-900/30 rounded px-2 py-1">{error}</p>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-2 p-4 border-t border-[var(--border-subtle)]">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-secondary)] transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={handleApply}
                disabled={applying || !recommended}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white hover:from-violet-700 hover:to-fuchsia-700 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {applying ? 'Application…' : 'Appliquer'}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
