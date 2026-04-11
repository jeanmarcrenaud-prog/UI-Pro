// useStream - WebSocket streaming hook
'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { apiService } from '@/services/api'

type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'error'

interface UseStreamOptions {
  onChunk?: (chunk: string) => void
  onDone?: () => void
}

export function useStream(options: UseStreamOptions = {}) {
  const [status, setStatus] = useState<StreamStatus>('idle')
  const wsRef = useRef<WebSocket | null>(null)
  const { updateMessage } = useChatStore()

  const connect = useCallback((messageId: string, message: string) => {
    setStatus('connecting')
    
    const ws = apiService.getWebSocket()
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('streaming')
      ws.send(message)
    }

    ws.onmessage = (event) => {
      const data = event.data
      
      if (data === '[DONE]') {
        setStatus('done')
        options.onDone?.()
        ws.close()
        return
      }
      
      // Update message content
      updateMessage(messageId, data, 'streaming')
      options.onChunk?.(data)
    }

    ws.onerror = () => {
      setStatus('error')
    }

    ws.onclose = () => {
      if (status !== 'error') {
        setStatus('idle')
      }
    }
  }, [updateMessage, options])

  const disconnect = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
    setStatus('idle')
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  return {
    status,
    connect,
    disconnect,
    isStreaming: status === 'streaming',
  }
}