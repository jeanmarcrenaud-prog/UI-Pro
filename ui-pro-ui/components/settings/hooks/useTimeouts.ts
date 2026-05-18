// hooks/useTimeouts.ts
import { useState, useEffect, useCallback } from 'react'
import type { SettingsMessage } from '../types'

export function useTimeouts() {
  const [llmTimeout, setLlmTimeout] = useState(300)
  const [executorTimeout, setExecutorTimeout] = useState(60)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<SettingsMessage | null>(null)

  // Load timeouts from API on mount
  useEffect(() => {
    fetch('/api/settings/timeouts')
      .then(r => r.json())
      .then(data => {
        if (data.llm_timeout) setLlmTimeout(data.llm_timeout)
        if (data.executor_timeout) setExecutorTimeout(data.executor_timeout)
      })
      .catch(() => {})
  }, [])

  const updateLlmTimeout = useCallback((value: number) => {
    if (value >= 10 && value <= 1800) {
      setLlmTimeout(value)
    }
  }, [])

  const updateExecutorTimeout = useCallback((value: number) => {
    if (value >= 5 && value <= 600) {
      setExecutorTimeout(value)
    }
  }, [])

  const saveTimeouts = useCallback(async (t: { settings: { savedSuccess: string; saveFailed: string } }) => {
    setIsSaving(true)
    setMessage(null)
    try {
      const res = await fetch('/api/settings/timeouts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ llm_timeout: llmTimeout, executor_timeout: executorTimeout }),
      })
      const data = await res.json()
      if (data.status === 'ok') {
        setLlmTimeout(data.llm_timeout)
        setExecutorTimeout(data.executor_timeout)
        setMessage({ type: 'success', text: t.settings.savedSuccess })
      } else {
        setMessage({ type: 'error', text: t.settings.saveFailed })
      }
    } catch {
      setMessage({ type: 'error', text: t.settings.saveFailed })
    } finally {
      setIsSaving(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }, [llmTimeout, executorTimeout])

return {
    llmTimeout,
    executorTimeout,
    setLlmTimeout: (v: number) => v >= 10 && v <= 1800 && setLlmTimeout(v),
    setExecutorTimeout: (v: number) => v >= 5 && v <= 600 && setExecutorTimeout(v),
    isSaving,
    message,
    saveTimeouts,
  }
}