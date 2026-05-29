// services/WebSocketManager.ts
// WebSocket connection lifecycle with heartbeat and reconnect logic

import { API_CONFIG } from '@/lib/config'
import { WS_EVENTS, RECONNECT, HEARTBEAT_INTERVAL, CONNECTION_TIMEOUT } from './constants'

export class WebSocketManager {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  async connect(onMessage: (data: any) => void, onClose: () => void): Promise<void> {
    if (this.isConnected) return

    return new Promise((resolve, reject) => {
      // Use relative URL so WebSocket goes through Next.js proxy
      // Browser resolves /ws relative to current origin (e.g. ws://localhost:3000/ws)
      // Next.js rewrites /ws/:path* to http://localhost:8000/ws/:path*
      const wsUrl = '/ws'

      console.log('[WebSocketManager] Connecting to:', wsUrl)
      this.ws = new WebSocket(wsUrl)

      const timeout = setTimeout(() => {
        this.ws?.close()
        reject(new Error('Connection timeout'))
      }, CONNECTION_TIMEOUT)

      this.ws.onopen = () => {
        clearTimeout(timeout)
        this.reconnectAttempts = 0
        this.startHeartbeat()
        console.log('[WebSocketManager] Connected')
        resolve()
      }

      this.ws.onerror = () => {
        clearTimeout(timeout)
        reject(new Error('Connection error'))
      }

      this.ws.onmessage = (e) => {
        try {
          const data = typeof e.data === 'string' ? JSON.parse(e.data) : e.data
          // Handle pong internally
          if (data.type === WS_EVENTS.PONG) return
          onMessage(data)
        } catch (err) {
          console.warn('[WS] Parse error:', err)
        }
      }

      this.ws.onclose = () => {
        this.stopHeartbeat()
        onClose()
      }
    })
  }

  send(payload: object): void {
    if (this.isConnected) {
      this.ws?.send(JSON.stringify(payload))
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatInterval = setInterval(() => {
      if (this.isConnected) {
        this.ws?.send(JSON.stringify({ type: WS_EVENTS.PING }))
      }
    }, HEARTBEAT_INTERVAL)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  close(): void {
    this.stopHeartbeat()
    this.ws?.close()
    this.ws = null
  }

  incrementReconnect(): number {
    return ++this.reconnectAttempts
  }

  getReconnectAttempts(): number {
    return this.reconnectAttempts
  }

  canReconnect(): boolean {
    return this.reconnectAttempts < RECONNECT.MAX_ATTEMPTS
  }

  resetReconnect(): void {
    this.reconnectAttempts = 0
  }

  calculateReconnectDelay(): number {
    const delay = RECONNECT.BASE_DELAY * Math.pow(RECONNECT.BACKOFF_FACTOR, this.reconnectAttempts)
    return Math.min(delay, RECONNECT.MAX_DELAY)
  }
}