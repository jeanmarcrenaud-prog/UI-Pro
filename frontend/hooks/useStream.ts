// useStream.ts
// Role: Custom hook for streaming - wraps StreamService, handles terminal events
// Used by chat components for token streaming

import { useEffect, useRef, useState, useCallback } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { streamService } from '@/services/streamService'

interface UseStreamOptions {
  url: string
  onToken?: (token: string) => void
  onStep?: (step: string) => void
  onDone?: () => void
  onError?: (error: Error) => void
}

interface UseStreamReturn {
  start: (prompt: string) => void
  stop: () => void
  isStreaming: boolean
  streamId: string | null
}

export function useStream({ url, onToken, onStep, onDone, onError }: UseStreamOptions): UseStreamReturn {
  const serviceRef = useRef<typeof streamService | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamId, setStreamId] = useState<string | null>(null)
  const { setCurrentStreamId, resetCurrentMessage } = useChatStore()

  // Register handlers and start stream
  const start = useCallback(async (prompt: string) => {
    setIsStreaming(true)
    setStreamId(`stream-${Date.now()}`)
    setCurrentStreamId(streamId)

    serviceRef.current = streamService

    try {
      await streamService.connect(prompt)
      
      streamService.onEvent((event) => {
        // Token event
        if (event.type === 'token' && event.content) {
          onToken?.(event.content)
        }
        // Step event (including stream_id, resumed, tool)
        if ((event.type === 'step' || event.type === 'tool') && event.stepId) {
          onStep?.(event.stepId)
        }
        // Done event
        if (event.type === 'done') {
          setIsStreaming(false)
          setCurrentStreamId(null)
          onDone?.()
        }
        // Error event
        if (event.type === 'error') {
          setIsStreaming(false)
          setCurrentStreamId(null)
          onError?.(new Error(event.error || 'Stream error'))
        }
        // Cancelled event
        if (event.type === 'cancelled') {
          setIsStreaming(false)
          setCurrentStreamId(null)
        }
      })
    } catch (err) {
      setIsStreaming(false)
      setCurrentStreamId(null)
      onError?.(err instanceof Error ? err : new Error(String(err)))
    }
  }, [url])

  const stop = useCallback(() => {
    streamService.close()
    setIsStreaming(false)
    setCurrentStreamId(null)
  }, [])

  useEffect(() => {
    return () => {
      streamService.close()
    }
  }, [])

  return { start, stop, isStreaming, streamId }
}