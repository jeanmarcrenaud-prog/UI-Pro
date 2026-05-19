// hooks/useBackendStatus.ts
import { useState, useCallback, useEffect } from 'react'
import { LLM_CONFIG } from '@/lib/config'
import type { BackendInfo } from '../types'

const initialBackends: BackendInfo[] = [
  { name: 'Ollama', url: LLM_CONFIG.ollamaUrl, status: 'inactive' },
  { name: 'LM Studio', url: LLM_CONFIG.lmstudioUrl, status: 'inactive' },
  { name: 'llama.cpp', url: LLM_CONFIG.llamacppUrl, status: 'inactive' },
  { name: 'Lemonade', url: LLM_CONFIG.lemonadeUrl, status: 'inactive' },
]

export function useBackendStatus() {
  const [backendInfo, setBackendInfo] = useState<BackendInfo[]>(initialBackends)
  const [isChecking, setIsChecking] = useState(false)

  const checkBackends = useCallback(async () => {
    setIsChecking(true)
    
    const results = await Promise.all(
      backendInfo.map(async (backend): Promise<BackendInfo> => {
        const endpoints = [
          { url: `${backend.url}/api/tags`, v1: false },
          { url: `${backend.url}/api/v1/models`, v1: true }
        ]
        let status: BackendInfo['status'] = 'inactive'
        let responseTime: number | undefined
        let modelCount = 0

        for (const endpoint of endpoints) {
          try {
            const controller = new AbortController()
            const timeoutId = setTimeout(() => controller.abort(), 2500)

            const startTime = Date.now()
            const res = await fetch(endpoint.url, { signal: controller.signal })
            responseTime = Date.now() - startTime
            clearTimeout(timeoutId)

            if (res.ok) {
              status = 'active'
              try {
                const data = await res.json()
                modelCount = data.models?.length || 0
              } catch {}
              break
            }
          } catch (err) {
            if (err instanceof Error && err.name !== 'AbortError') {
              status = 'error'
            }
          }
        }
        return { ...backend, status, responseTime, modelCount, lastChecked: Date.now() }
      })
    )
    
    setBackendInfo(results)
    setIsChecking(false)
  }, [backendInfo])

  // Check backend connectivity once on mount
  useEffect(() => {
    checkBackends()
  }, [checkBackends])

  return { backendInfo, checkBackends, isChecking }
}