// useStream.ts
// Role: Custom hook for streaming - wraps StreamService, handles terminal events
// Used by chat components for token streaming

import { useEffect, useRef, useState, useCallback } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { createStreamService, type StreamChunk } from '@/services/streamService'
import { STREAM_EVENTS } from '@/lib/events'

interface UseStreamOptions {
  url: string
  mode?: 'websocket' | 'sse'
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
  const serviceRef = useRef<ReturnType<typeof createStreamService> | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamId, setStreamId] = useState<string | null>(null)
  const { setCurrentStreamId, resetCurrentMessage } = useChatStore()

  const start = useCallback(async (prompt: string) => {
    setIsStreaming(true)
    setStreamId(`stream-${Date.now()}`)
    setCurrentStreamId(streamId)

    const service = createStreamService({
      url,
      mode: 'sse',
      onChunk: (chunk: StreamChunk) => {
        if (chunk.type === STREAM_EVENTS.TOKEN && chunk.content) {
          onToken?.(chunk.content)
        }
        if (chunk.type === STREAM_EVENTS.STEP && chunk.step) {
          onStep?.(chunk.step)
        }
      },
      onDone: () => {
        setIsStreaming(false)
        setCurrentStreamId(null)
        onDone?.()
      },
      onError: (error: Error) => {
        setIsStreaming(false)
        setCurrentStreamId(null)
        onError?.(error)
      },
      onCancelled: () => {
        setIsStreaming(false)
        setCurrentStreamId(null)
      },
    })

    serviceRef.current = service

    try {
      await service.connect()
      service.send({ prompt, stream_id: streamId })
    } catch (err) {
      setIsStreaming(false)
      setCurrentStreamId(null)
      onError?.(err instanceof Error ? err : new Error(String(err)))
    }
  }, [url])

  const stop = useCallback(() => {
    serviceRef.current?.close()
    setIsStreaming(false)
    setCurrentStreamId(null)
    resetCurrentMessage()
  }, [])

  useEffect(() => {
    return () => {
      serviceRef.current?.close()
    }
  }, [])

  return { start, stop, isStreaming, streamId }
}