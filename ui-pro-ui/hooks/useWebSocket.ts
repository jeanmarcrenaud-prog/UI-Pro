import { useRef } from 'react'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)

  const connect = (url: string, handlers: any) => {
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = handlers.onOpen
    ws.onmessage = handlers.onMessage
    ws.onerror = handlers.onError
    ws.onclose = handlers.onClose
  }

  const send = (data: any) => {
    wsRef.current?.send(JSON.stringify(data))
  }

  const close = () => {
    wsRef.current?.close()
  }

  return { connect, send, close }
}