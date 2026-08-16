// hooks/useHermesSettings.ts
import { useState, useEffect, useCallback } from 'react'
import type { SettingsMessage } from '../types'

// Hermes MCP LLM endpoint (ADR D3). The backend persists these to .env
// via POST /api/settings (set_hermes_llm_config). The MCP server reads
// them at construction (first get_server() call), so the change takes
// effect on the next process restart — the UI notes this next to the
// save button.
export function useHermesSettings() {
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('google/gemma-4-12b-qat')
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<SettingsMessage | null>(null)

  // Load current Hermes LLM config from API on mount
  useEffect(() => {
    fetch('/api/settings')
      .then(r => r.json())
      .then(data => {
        if (data.hermes_llm_base_url) setBaseUrl(data.hermes_llm_base_url)
        if (data.hermes_llm_model) setModel(data.hermes_llm_model)
      })
      .catch(() => {})
  }, [])

  const saveHermesConfig = useCallback(async (t: { settings: { savedSuccess: string; saveFailed: string } }) => {
    setIsSaving(true)
    setMessage(null)
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hermes_llm_base_url: baseUrl,
          hermes_llm_model: model,
        }),
      })
      const data = await res.json()
      if (data.status === 'ok') {
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
  }, [baseUrl, model])

  return {
    baseUrl,
    model,
    setBaseUrl,
    setModel,
    isSaving,
    message,
    saveHermesConfig,
  }
}