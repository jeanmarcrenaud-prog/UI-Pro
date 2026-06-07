// hooks/useTimeouts.ts
import { useState, useEffect, useCallback } from 'react'
import type { SettingsMessage } from '../types'

// LLM_TIMEOUT floor raised 10s→30s in commit 4a3b40b (validated
// server-side by Field(ge=30) on Settings.llm_timeout). Mirroring
// the floor in the input guard keeps the UI from displaying a value
// the backend will silently clamp to 30.
const LLM_TIMEOUT_FLOOR = 30
const LLM_TIMEOUT_CEIL = 1800
const EXECUTOR_TIMEOUT_FLOOR = 5
const EXECUTOR_TIMEOUT_CEIL = 600

export function useTimeouts() {
  const [llmTimeout, setLlmTimeout] = useState(300)
  const [executorTimeout, setExecutorTimeout] = useState(60)
  const [isSaving, setIsSaving] = useState(false)
  const [isReloading, setIsReloading] = useState(false)
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
    if (value >= LLM_TIMEOUT_FLOOR && value <= LLM_TIMEOUT_CEIL) {
      setLlmTimeout(value)
    }
  }, [])

  const updateExecutorTimeout = useCallback((value: number) => {
    if (value >= EXECUTOR_TIMEOUT_FLOOR && value <= EXECUTOR_TIMEOUT_CEIL) {
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
        setMessage({ type: 'error', text: data.message || t.settings.saveFailed })
      }
    } catch {
      setMessage({ type: 'error', text: t.settings.saveFailed })
    } finally {
      setIsSaving(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }, [llmTimeout, executorTimeout])

  // Hot-reload from .env. Use this when the user has edited .env by
  // hand (e.g. bumped LLM_TIMEOUT=1800 in vim) — POST /api/settings/reload
  // re-reads the file, revalidates, and mutates the in-memory Settings
  // singleton in place. On success, we sync the form values from the
  // server response so the UI matches reality. On ValidationError
  // (bad value below the 30s floor) the server keeps the old values
  // and the form is left unchanged.
  const reloadFromEnv = useCallback(async (t: { settings: { reloadSuccess: string; reloadFailed: string } }) => {
    setIsReloading(true)
    setMessage(null)
    try {
      const res = await fetch('/api/settings/reload', { method: 'POST' })
      const data = await res.json()
      if (data.status === 'ok') {
        if (typeof data.llm_timeout === 'number') setLlmTimeout(data.llm_timeout)
        if (typeof data.executor_timeout === 'number') setExecutorTimeout(data.executor_timeout)
        setMessage({ type: 'success', text: t.settings.reloadSuccess })
      } else {
        setMessage({ type: 'error', text: data.message || t.settings.reloadFailed })
      }
    } catch {
      setMessage({ type: 'error', text: t.settings.reloadFailed })
    } finally {
      setIsReloading(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }, [])

return {
    llmTimeout,
    executorTimeout,
    setLlmTimeout: (v: number) => v >= LLM_TIMEOUT_FLOOR && v <= LLM_TIMEOUT_CEIL && setLlmTimeout(v),
    setExecutorTimeout: (v: number) => v >= EXECUTOR_TIMEOUT_FLOOR && v <= EXECUTOR_TIMEOUT_CEIL && setExecutorTimeout(v),
    isSaving,
    isReloading,
    message,
    saveTimeouts,
    reloadFromEnv,
  }
}