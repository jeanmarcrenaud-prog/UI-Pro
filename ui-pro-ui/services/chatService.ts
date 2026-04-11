// Chat Service - Business logic for chat
import type { Message } from '@/lib/types'

type MessageHandler = (message: Message) => void
type StatusHandler = (status: 'idle' | 'connecting' | 'streaming' | 'error') => void

class ChatService {
  private ws: WebSocket | null = null
  private messageHandler: MessageHandler | null = null
  private statusHandler: StatusHandler | null = null
  private baseUrl: string

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl
  }

  onMessage(handler: MessageHandler) {
    this.messageHandler = handler
  }

  onStatus(handler: StatusHandler) {
    this.statusHandler = handler
  }

  async sendMessage(content: string): Promise<void> {
    this.setStatus('connecting')

    // Try WebSocket first
    try {
      const wsUrl = `ws://${window.location.hostname}:8000/ws`
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.setStatus('streaming')
        this.ws?.send(JSON.stringify({ message: content }))
      }

      this.ws.onmessage = (event) => {
        const data = event.data
        if (data === '[DONE]') {
          this.disconnect()
          return
        }
        this.messageHandler?.({
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: data,
          status: 'streaming',
        })
      }

      this.ws.onerror = () => {
        this.disconnect()
        this.fetchREST(content)
      }

      this.ws.onclose = () => {
        this.setStatus('idle')
      }
    } catch {
      this.fetchREST(content)
    }
  }

  private async fetchREST(content: string): Promise<void> {
    this.setStatus('connecting')

    try {
      const response = await fetch(`${this.baseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content }),
      })

      const data = await response.json()

      this.messageHandler?.({
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: data.result || data.error || 'No response',
        status: data.status === 'error' ? 'error' : 'done',
      })
    } catch (error) {
      this.messageHandler?.({
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: error instanceof Error ? error.message : 'Connection failed',
        status: 'error',
      })
    } finally {
      this.setStatus('idle')
    }
  }

  private setStatus(status: 'idle' | 'connecting' | 'streaming' | 'error') {
    this.statusHandler?.(status)
  }

  disconnect() {
    this.ws?.close()
    this.ws = null
  }
}

export const chatService = new ChatService()