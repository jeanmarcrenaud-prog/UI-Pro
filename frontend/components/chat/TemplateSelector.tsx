// TemplateSelector.tsx
// Role: Modal selector for project templates — pre-fills the chat prompt
//       with the template's prompt_suffix when a template is chosen.

'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { LayoutTemplate, X, Sparkles } from 'lucide-react'

export interface TemplateInfo {
  id: string
  name: string
  description: string
}

interface TemplateSelectorProps {
  /** Trigger button is rendered by the parent; pass isOpen + handlers. */
  isOpen: boolean
  onClose: () => void
  /** Called with the composed prompt when a template is selected. */
  onSelect: (prompt: string) => void
}

// Human-readable icons per template id (fallback to Sparkles)
const TEMPLATE_ICONS: Record<string, string> = {
  'nextjs-app': '⚛️',
  fastapi: '🐍',
  tauri: '🦀',
}

export function TemplateSelector({ isOpen, onClose, onSelect }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<TemplateInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return

    let cancelled = false
    setLoading(true)
    setError(null)

    fetch('/api/templates')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: TemplateInfo[]) => {
        if (!cancelled) {
          setTemplates(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load templates')
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [isOpen])

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])

  const handleSelect = useCallback(
    (template: TemplateInfo) => {
      const prompt = `Create a ${template.name} project. ${template.description}`
      onSelect(prompt)
      onClose()
    },
    [onSelect, onClose],
  )

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
            className="relative w-full max-w-2xl mx-4 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl"
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 12 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b border-slate-700">
              <div className="flex items-center gap-2">
                <LayoutTemplate className="w-5 h-5 text-violet-400" />
                <h2 className="text-lg font-semibold text-white">Project Templates</h2>
              </div>
              <button
                onClick={onClose}
                className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 max-h-[60vh] overflow-y-auto">
              {loading && (
                <div className="text-center py-8 text-slate-400">
                  <div className="animate-spin w-6 h-6 border-2 border-violet-500/30 border-t-violet-500 rounded-full mx-auto mb-3" />
                  <p>Loading templates…</p>
                </div>
              )}

              {error && !loading && (
                <div className="text-center py-8 text-slate-400">
                  <p className="text-red-400 mb-1">Failed to load templates</p>
                  <p className="text-sm">{error}</p>
                </div>
              )}

              {!loading && !error && templates.length === 0 && (
                <div className="text-center py-8 text-slate-400">
                  <p>No templates available.</p>
                </div>
              )}

              {!loading && !error && templates.length > 0 && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {templates.map((template) => (
                    <motion.div
                      key={template.id}
                      className="group p-4 bg-slate-800/50 border border-slate-700 hover:border-violet-500/50 rounded-xl transition-colors cursor-pointer"
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.99 }}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-2xl" role="img" aria-hidden>
                          {TEMPLATE_ICONS[template.id] || '✨'}
                        </span>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium text-white group-hover:text-violet-300 transition-colors">
                            {template.name}
                          </h3>
                          <p className="text-sm text-slate-400 mt-1 line-clamp-2">
                            {template.description}
                          </p>
                        </div>
                      </div>

                      <button
                        onClick={() => handleSelect(template)}
                        className="mt-3 w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        Use template
                      </button>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/**
 * Standalone trigger button — renders a "Templates" icon button that opens
 * the selector.  Use this when you don't need to control `isOpen` yourself.
 */
export function TemplateSelectorTrigger({
  onSelect,
  disabled,
}: {
  onSelect: (prompt: string) => void
  disabled?: boolean
}) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        disabled={disabled}
        className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Choose a project template"
        title="Templates"
      >
        <LayoutTemplate className="w-4 h-4" />
      </button>

      <TemplateSelector
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        onSelect={onSelect}
      />
    </>
  )
}
