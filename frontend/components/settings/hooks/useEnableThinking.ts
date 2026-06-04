// hooks/useEnableThinking.ts
// Manages the LLM thinking-mode toggle. When OFF (default), the
// OpenAI-compat mixin injects `chat_template_kwargs={"enable_thinking": false}`
// so Qwen3.5+ / o1 / DeepSeek-R1 don't burn the entire `max_tokens`
// budget on internal chain-of-thought. When ON, the model is free
// to reason internally (useful for o1-style workflows).
//
// Auto-saves on toggle — the change is server-side and takes effect
// on the very next LLM call, so a Save button would be friction
// without value.

import { useState, useEffect, useCallback, useRef } from 'react'
import type { SettingsMessage } from '../types'

export function useEnableThinking() {
  const [enabled, setEnabled] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<SettingsMessage | null>(null)
  // Skip the auto-save that the on-mount fetch would otherwise trigger.
  const hasMounted = useRef(false)

  // Load current value on mount
  useEffect(() => {
    fetch('/api/settings/llm-enable-thinking')
      .then(r => r.json())
      .then(data => {
        if (data && typeof data.enabled === 'boolean') {
          setEnabled(data.enabled)
        }
        hasMounted.current = true
      })
      .catch(() => {
        hasMounted.current = true
      })
      .finally(() => setIsLoading(false))
  }, [])

  // Persist whenever the value flips (after the initial mount load)
  useEffect(() => {
    if (!hasMounted.current) return
    let cancelled = false
    setIsSaving(true)
    setMessage(null)
    fetch('/api/settings/llm-enable-thinking', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
      .then(r => r.json())
      .then(data => {
        if (cancelled) return
        if (data.status === 'ok') {
          setMessage({
            type: 'success',
            text: enabled
              ? 'Thinking enabled — model may spend tokens on internal reasoning.'
              : 'Thinking disabled — model jumps straight to the answer.',
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
  }, [enabled])

  const toggle = useCallback(() => {
    setEnabled(prev => !prev)
  }, [])

  return { enabled, isLoading, isSaving, message, toggle }
}
