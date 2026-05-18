// hooks/useModelDescription.ts
import { useState, useEffect, useCallback } from 'react'
import { LLM_CONFIG } from '@/lib/config'

export function useModelDescription(selectedModel: string | null) {
  const [description, setDescription] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const fetchDescription = useCallback(async () => {
    if (!selectedModel || selectedModel === 'default') {
      setDescription(null)
      return
    }
    
    setIsLoading(true)
    try {
      // Try GitHub API first with timeout
      const githubController = new AbortController()
      const githubTimeout = setTimeout(() => githubController.abort(), 3000)
      const githubRes = await fetch(
        `https://api.github.com/search/repositories?q=${encodeURIComponent(selectedModel)}+in:name&per_page=1`,
        { signal: githubController.signal, headers: { Accept: 'application/vnd.github.v3+json' } }
      )
      clearTimeout(githubTimeout)

      if (githubRes.ok) {
        const data = await githubRes.json()
        if (data.items?.[0]?.description) {
          setDescription(data.items[0].description)
          setIsLoading(false)
          return
        }
      } else if (!githubRes.ok && githubRes.status !== 429) {
        console.warn(`GitHub API error: ${githubRes.status}`)
      }

      // Try Ollama API as fallback with timeout
      const ollamaController = new AbortController()
      const ollamaTimeout = setTimeout(() => ollamaController.abort(), 3000)
      const ollamaRes = await fetch(`${LLM_CONFIG.ollamaUrl}/api/tags`, {
        signal: ollamaController.signal
      })
      clearTimeout(ollamaTimeout)

      if (ollamaRes.ok) {
        const ollamaData = await ollamaRes.json()
        const model = ollamaData.models?.find((m: any) => m.name === selectedModel)
        if (model?.details?.description) {
          setDescription(model.details.description)
          setIsLoading(false)
          return
        }
      }
      setDescription('Large language model from Ollama')
    } catch (err) {
      console.warn('Failed to fetch model description:', err)
      setDescription('Large language model')
    } finally {
      setIsLoading(false)
    }
  }, [selectedModel])

  // Fetch model description when selected model changes
  useEffect(() => {
    fetchDescription()
  }, [fetchDescription])

  return { description, isLoading, refetch: fetchDescription }
}