// hooks/useLogLevel.ts
import { useState, useEffect, useCallback } from 'react'
import type { SettingsMessage } from '../types'

const AVAILABLE_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

export function useLogLevel() {
  const [currentLevel, setCurrentLevel] = useState('INFO')
  const [availableLevels] = useState(AVAILABLE_LEVELS)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<SettingsMessage | null>(null)

  // Load log level from API on mount
  useEffect(() => {
    fetch('/api/logs/level')
      .then(r => r.json())
      .then(data => {
        if (data.current_level) setCurrentLevel(data.current_level)
      })
      .catch(() => {})
  }, [])

  const setLevel = useCallback((level: string) => {
    setCurrentLevel(level)
  }, [])

  const saveLevel = useCallback(async (t: { settings: { savedSuccess: string; saveFailed: string } }) => {
    setIsSaving(true)
    setMessage(null)
    try {
      const res = await fetch('/api/logs/level', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level: currentLevel }),
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const data = await res.json()
      if (data.current_level) {
        setCurrentLevel(data.current_level)
        setMessage({ type: 'success', text: t.settings.savedSuccess })
      } else {
        throw new Error('Invalid response format')
      }
    } catch (error) {
      console.error('Log level save error:', error)
      setMessage({ type: 'error', text: t.settings.saveFailed })
    } finally {
      setIsSaving(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }, [currentLevel])

  return {
    currentLevel,
    availableLevels,
    isSaving,
    message,
    setLevel,
    saveLevel,
  }
}