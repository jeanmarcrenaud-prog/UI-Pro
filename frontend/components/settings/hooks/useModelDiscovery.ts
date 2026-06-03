// hooks/useModelDiscovery.ts
import { useState, useCallback, useMemo } from 'react'
import { modelDiscovery } from '@/services/modelDiscovery'
import { useUIStore } from '@/lib/stores/uiStore'

export function useModelDiscovery() {
  const { availableModels, selectedModel, setSelectedModel } = useUIStore()
  
  const [search, setSearch] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Memoized filtered models based on search
  const filteredModels = useMemo(() =>
    availableModels.filter(model =>
      model.name.toLowerCase().includes(search.toLowerCase()) ||
      model.provider.toLowerCase().includes(search.toLowerCase())
    ),
    [availableModels, search]
  )

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true)
    setError(null)

    try {
      // force=true bypasses the backend's 5-min TTL cache so backends
      // that came online after the API started (e.g. user launched
      // LM Studio mid-session) are picked up immediately.
      await modelDiscovery.discover(true)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to refresh models'
      setError(message)
      console.error('Model discovery failed:', err)
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  const handleSelectModel = useCallback((modelId: string) => {
    setSelectedModel(modelId)
  }, [setSelectedModel])

  const selectedModelInfo = useMemo(() => 
    availableModels.find(m => m.id === selectedModel),
    [availableModels, selectedModel]
  )

  return {
    models: availableModels,
    filteredModels,
    selectedModel,
    selectedModelInfo,
    search,
    isRefreshing,
    error,
    setSearch,
    handleRefresh,
    handleSelectModel,
  }
}