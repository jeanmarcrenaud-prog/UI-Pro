// NodeRoutingSettings.tsx
// Toggle for per-node model routing. When ON, each pipeline node uses
// the preset tier (analyzing=fast, plan/code/review=reasoning) instead
// of the user-selected chat model. When OFF, every node uses the chat
// model (legacy behavior).

'use client'

import { useNodeRouting } from './hooks/useNodeRouting'

export function NodeRoutingSettings() {
  const { enabled, routing, models, isLoading, isSaving, message, toggle } = useNodeRouting()

  return (
    <section className="glass-panel rounded-xl p-4 hover:border-violet-500/30 transition-all duration-200 hover:shadow-[0_0_20px_rgba(168,85,247,0.1)]">
      <h3 className="text-[11px] uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
        🧭 Per-Node Routing
      </h3>

      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-xs text-slate-300 leading-relaxed">
            Route each pipeline node to its preset tier instead of the chat model.
          </p>
          <p className="text-[10px] text-slate-500 mt-1">
            {enabled
              ? 'A 1.2B model handles classification; plan/code/review use the reasoning slot.'
              : 'Every node uses the chat model (legacy). Small models will struggle with code gen.'}
          </p>
        </div>

        <button
          onClick={toggle}
          disabled={isLoading}
          role="switch"
          aria-checked={enabled}
          aria-label="Toggle per-node model routing"
          className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-violet-500/50 ${
            enabled ? 'bg-violet-600' : 'bg-slate-600'
          } ${isLoading ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-lg transition-transform ${
              enabled ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {/* Routing table — visible only when toggle is on */}
      {enabled && !isLoading && (
        <div className="mt-3 pt-3 border-t border-slate-700/40 space-y-1.5">
          <RoutingRow
            label="Analyze"
            tier="fast"
            model={models.fast}
            current={routing.analyzing_node}
          />
          <RoutingRow
            label="Plan"
            tier="reasoning"
            model={models.reasoning}
            current={routing.planning_node}
          />
          <RoutingRow
            label="Code"
            tier="reasoning"
            model={models.reasoning}
            current={routing.coding_node}
          />
          <RoutingRow
            label="Review"
            tier="reasoning"
            model={models.reasoning}
            current={routing.reviewing_node}
          />
        </div>
      )}

      {/* Status line */}
      <div className="mt-2 flex items-center gap-2 min-h-[16px]">
        {isSaving && (
          <span className="text-[10px] text-slate-500">⏳ saving...</span>
        )}
        {message && (
          <p
            className={`text-[10px] ${
              message.type === 'success' ? 'text-emerald-400' : 'text-red-400'
            }`}
          >
            {message.type === 'success' ? '✅' : '⚠️'} {message.text}
          </p>
        )}
      </div>
    </section>
  )
}

function RoutingRow({
  label,
  tier,
  model,
  current,
}: {
  label: string
  tier: string
  model: string
  current: string
}) {
  return (
    <div className="flex items-center justify-between text-[10px] gap-2">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-slate-400 w-14 flex-shrink-0">{label}</span>
        <span
          className={`px-1.5 py-0.5 rounded text-[9px] uppercase tracking-wide ${
            current === tier
              ? 'bg-violet-600/20 text-violet-300'
              : 'bg-slate-700/50 text-slate-500'
          }`}
        >
          {current}
        </span>
      </div>
      <span className="text-slate-500 font-mono truncate text-right" title={model || '(unset)'}>
        {model || '(unset)'}
      </span>
    </div>
  )
}
