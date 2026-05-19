// useWebSocket.ts
// Role: Custom hook for WebSocket connections with reconnection, heartbeat, and resume support
// Recommended for streaming layer (SSE alternative when bidirectional needed)

import { useEffect, useRef, useCallback, useState } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { STREAM_EVENTS } from '@/lib/events'

const MAX_RECONNECT_ATTEMPTS = 6
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 32000] // Exponential backoff
const HEARTBEAT_INTERVAL = 25000 // 25s

interface UseWebSocketOptions {
  url: string
  onMessage?: (data: unknown) => void
  onError?: (error: Error) => void
  onOpen?: () => void
  onClose?: () => void
}

interface UseWebSocketReturn {
  send: (data: unknown) => void
  close: () => void
  isConnected: boolean
  reconnectAttempts: number
}

export function useWebSocket({ url, onMessage, onError, onOpen, onClose }: UseWebSocketOptions): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const [isConnected, setIsConnected] = useState(false)
  const { currentStreamId, lastReceivedChunkIndex, setCurrentStreamId, updateLastChunkIndex } = useChatStore()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      reconnectAttemptsRef.current = 0
      onOpen?.()

      // Start heartbeat
      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, HEARTBEAT_INTERVAL)

      // Resume if needed
      if (currentStreamId && lastReceivedChunkIndex > 0) {
        ws.send(JSON.stringify({
          action: 'resume',
          stream_id: currentStreamId,
          last_index: lastReceivedChunkIndex,
        }))
      }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch {
        onMessage?.(event.data)
      }
    }

    ws.onerror = (event) => {
      const error = new Error('WebSocket error')
      onError?.(error)
    }

    ws.onclose = () => {
      setIsConnected(false)
      onClose?.()

      // Clear heartbeat
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current)
        heartbeatRef.current = null
      }

      // Exponential backoff reconnection
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = RECONNECT_DELAYS[reconnectAttemptsRef.current] || RECONNECT_DELAYS[RECONNECT_DELAYS.length - 1]
        setTimeout(() => {
          reconnectAttemptsRef.current++
          connect()
        }, delay)
      }
    }
  }, [url])

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const close = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current)
    }
    wsRef.current?.close()
    wsRef.current = null
    setIsConnected(false)
  }, [])

  useEffect(() => {
    connect()
    return close
  }, [url])

  return {
    send,
    close,
    isConnected,
    reconnectAttempts: reconnectAttemptsRef.current,
  }
}

// Helper to map stream events
export function mapStreamEvent(data: Record<string, unknown>): { type: string; payload: unknown } | null {
  // Expected format from backend StreamChunk.to_dict()
  if (data.type === STREAM_EVENTS.TOKEN) {
    return { type: STREAM_EVENTS.TOKEN, payload: data.content }
  }
  if (data.type === STREAM_EVENTS.STEP) {
    return { type: STREAM_EVENTS.STEP, payload: data.step }
  }
  if (data.type === STREAM_EVENTS.DONE) {
    return { type: STREAM_EVENTS.DONE, payload: data }
  }
  if (data.type === STREAM_EVENTS.ERROR) {
    return { type: STREAM_EVENTS.ERROR, payload: data.error }
  }
  if (data.type === STREAM_EVENTS.CANCELLED) {
    return { type: STREAM_EVENTS.CANCELLED, payload: data }
  }
  return null
}