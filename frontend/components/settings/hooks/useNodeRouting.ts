// hooks/useNodeRouting.ts
// Manages the per-node model routing toggle (analyze=fast, plan/code/review=reasoning).
// Auto-saves on toggle — the change is server-side and takes effect on the next
// pipeline run, so a Save button would be friction without value.

import { useState, useEffect, useCallback, useRef } from 'react'
import type { SettingsMessage } from '../types'

interface NodeRoutingState {
  enabled: boolean
  routing: {
    analyzing_node: 'fast' | 'user_model'
    planning_node: 'reasoning' | 'user_model'
    coding_node: 'reasoning' | 'user_model'
    reviewing_node: 'reasoning' | 'user_model'
  }
  models: {
    fast: string
    reasoning: string
    code: string
  }
}

const DEFAULT_STATE: NodeRoutingState = {
  enabled: true,
  routing: {
    analyzing_node: 'fast',
    planning_node: 'reasoning',
    coding_node: 'reasoning',
    reviewing_node: 'reasoning',
  },
  models: { fast: '', reasoning: '', code: '' },
}

export function useNodeRouting() {
  const [state, setState] = useState<NodeRoutingState>(DEFAULT_STATE)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<SettingsMessage | null>(null)
  // Skip the auto-save that the on-mount fetch would otherwise trigger.
  const hasMounted = useRef(false)

  // Load current routing state on mount
  useEffect(() => {
    fetch('/api/settings/node-routing')
      .then(r => r.json())
      .then(data => {
        if (data && typeof data.enabled === 'boolean') {
          setState({
            enabled: data.enabled,
            routing: data.routing ?? DEFAULT_STATE.routing,
            models: data.models ?? DEFAULT_STATE.models,
          })
        }
        hasMounted.current = true
      })
      .catch(() => {
        hasMounted.current = true
      })
      .finally(() => setIsLoading(false))
  }, [])

  // Persist whenever `enabled` flips (after the initial mount load)
  useEffect(() => {
    if (!hasMounted.current) return
    let cancelled = false
    setIsSaving(true)
    setMessage(null)
    fetch('/api/settings/node-routing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: state.enabled }),
    })
      .then(r => r.json())
      .then(data => {
        if (cancelled) return
        if (data.status === 'ok') {
          setMessage({
            type: 'success',
            text: state.enabled
              ? 'Per-node routing enabled — analyze/plan/code/review use preset tiers.'
              : 'Per-node routing disabled — all nodes use the chat model.',
          })
        } else {
          setMessage({ type: 'error', text: data.message || 'Failed to save' })
        }
      })
      .catch(() => {
        if (cancelled) return
        setMessage({ type: 'error', text: 'Network error' })
      })
      .finally(() => {
        if (cancelled) return
        setIsSaving(false)
        setTimeout(() => setMessage(null), 3000)
      })
    return () => {
      cancelled = true
    }
  }, [state.enabled])

  const toggle = useCallback(() => {
    setState(prev => ({ ...prev, enabled: !prev.enabled }))
  }, [])

  return {
    enabled: state.enabled,
    routing: state.routing,
    models: state.models,
    isLoading,
    isSaving,
    message,
    toggle,
  }
}
