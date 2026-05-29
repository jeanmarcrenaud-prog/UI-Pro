// sidebar/ModelSelectDropdown.tsx
// Role: Dropdown component for model selection

'use client'

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
  return (
    <div className="relative">
      <AnimatePresence>
        {isLoading ? (
          <ModelDiscoveryIndicator />
        ) : (
          <select
            value={selectedModel}
            onChange={(e) => onModelChange(e.target.value)}
            className="
              appearance-none 
              w-full 
              bg-slate-800/80 
              border border-slate-700/60 
              text-slate-200 
              text-xs 
              rounded-xl 
              px-3 py-2.5 
              focus:outline-none 
              focus:border-violet-500/60 
              focus:ring-2 
              focus:ring-violet-500/20 
              transition-all duration-200
              pr-16
            "
            aria-label="Select language model"
            aria-describedby="model-help"
          >
            {availableModels.length === 0 ? (
              <option value="" disabled>
                t.sidebar.noModelsFound
              </option>
            ) : (
              availableModels.map((model) => {
                // Build display string with metadata
                const parts = [model.name]
                if (model.sizeGb) parts.push(`${model.sizeGb}GB`)
                if (model.speedTier && model.speedTier !== 'fast') parts.push(model.speedTier)
                parts.push(model.provider)

                return (
                  <option
                    key={`${model.provider}-${model.id}`}
                    value={model.id}
                  >
                    {parts.join(' • ')}
                  </option>
                )
              })
            )}
          </select>
        )}
      </AnimatePresence>

      {/* Help text */}
      <span
        id="model-help"
        className="
          absolute 
          right-3 
          top-1/2 
          -translate-y-1/2 
          text-xs 
          text-slate-500 
          pointer-events-none
        "
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </span>
    </div>
  )
}
