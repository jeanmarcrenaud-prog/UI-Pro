// sidebar/ModelSelectDropdown.tsx
// Role: Custom dropdown for model selection with visible loaded-in-VRAM state

'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ModelDiscoveryIndicator } from './ModelDiscoveryIndicator'

// ModelInfo type matching the rich metadata used by the sidebar
export interface ModelInfo {
  id: string
  name: string
  provider: string
  parameterSize?: string
  quantization?: string
  sizeGb?: number
  maxContext?: number
  speedTier?: 'very_fast' | 'fast' | 'medium' | 'slow'
  isCoder?: boolean
  isReasoning?: boolean
  isVision?: boolean
  capabilities?: string[]
  isLoaded?: boolean
  sizeVramGb?: number
}

export function ModelSelectDropdown({
  isLoading,
  availableModels,
  selectedModel,
  onModelChange
}: {
  isLoading: boolean
  availableModels: ModelInfo[]
  selectedModel: string
  onModelChange: (model: string) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selected = useMemo(
    () => availableModels.find(m => m.id === selectedModel),
    [availableModels, selectedModel]
  )

  const loadedCount = useMemo(
    () => availableModels.filter(m => m.isLoaded).length,
    [availableModels]
  )

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="relative" ref={containerRef}>
      <AnimatePresence>
        {isLoading ? (
          <ModelDiscoveryIndicator />
        ) : (
          <div className="space-y-1.5">
            <button
              type="button"
              onClick={() => setOpen(o => !o)}
              aria-haspopup="listbox"
              aria-expanded={open}
              aria-label="Select language model"
              className="
                appearance-none
                w-full
                bg-slate-800/80
                border border-slate-700/60
                text-slate-200
                text-xs
                rounded-xl
                px-3 py-2.5
                text-left
                focus:outline-none
                focus:border-violet-500/60
                focus:ring-2
                focus:ring-violet-500/20
                transition-all duration-200
                pr-9
                flex items-center justify-between gap-2
              "
            >
              <span className="flex items-center gap-2 min-w-0">
                {selected?.isLoaded && (
                  <span
                    className="relative flex w-2 h-2 shrink-0"
                    title="Loaded in VRAM"
                  >
                    <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-50" />
                    <span className="relative w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]" />
                  </span>
                )}
                <span className="truncate">
                  {selected ? selected.name : 'Select a model'}
                </span>
                {selected?.provider && (
                  <span className="text-[10px] text-slate-500 shrink-0">
                    {selected.provider}
                  </span>
                )}
              </span>
              <svg
                className={`w-3 h-3 text-slate-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            <AnimatePresence>
              {open && (
                <motion.ul
                  role="listbox"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.12 }}
                  className="
                    absolute z-50 mt-1 w-full
                    bg-slate-900
                    border border-slate-700/70
                    rounded-xl
                    shadow-2xl shadow-black/40
                    py-1
                    max-h-80 overflow-y-auto
                  "
                >
                  {availableModels.length === 0 && (
                    <li className="px-3 py-2 text-xs text-slate-500 italic">
                      No models discovered
                    </li>
                  )}
                  {availableModels.map((model) => {
                    const isSelected = model.id === selectedModel
                    return (
                      <li
                        key={`${model.provider}-${model.id}`}
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => {
                          onModelChange(model.id)
                          setOpen(false)
                        }}
                        className={`
                          flex items-center gap-2.5 px-3 py-2 text-xs cursor-pointer
                          transition-colors duration-100
                          ${isSelected ? 'bg-violet-600/20 text-white' : 'text-slate-200 hover:bg-slate-800/80'}
                        `}
                      >
                        <span className="relative flex w-2.5 h-2.5 shrink-0">
                          {model.isLoaded ? (
                            <>
                              <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-50" />
                              <span className="relative w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
                            </>
                          ) : (
                            <span className="w-2.5 h-2.5 rounded-full border border-slate-600" />
                          )}
                        </span>
                        <span className="flex-1 min-w-0 truncate">
                          {model.name}
                        </span>
                        {model.isLoaded && (
                          <span className="text-[10px] text-emerald-400 font-semibold uppercase tracking-wide shrink-0">
                            {model.sizeVramGb ? `${model.sizeVramGb}GB` : 'VRAM'}
                          </span>
                        )}
                        {model.sizeGb && !model.isLoaded && (
                          <span className="text-[10px] text-slate-500 shrink-0">
                            {model.sizeGb}GB
                          </span>
                        )}
                        <span className="text-[10px] text-slate-500 shrink-0">
                          {model.provider}
                        </span>
                      </li>
                    )
                  })}
                </motion.ul>
              )}
            </AnimatePresence>

            {/* Loaded models summary badge */}
            {loadedCount > 0 && (
              <div className="flex items-center gap-1.5 px-1">
                <span className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-semibold">
                  <span className="relative flex w-2 h-2">
                    <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-40" />
                    <span className="relative w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
                  </span>
                  {loadedCount} model{loadedCount > 1 ? 's' : ''} in VRAM
                </span>
              </div>
            )}
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}
