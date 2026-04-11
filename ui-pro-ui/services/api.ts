// API Service - Communication with FastAPI backend
import type { ChatRequest, ChatResponse } from '@/lib/types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export class ApiService {
  private baseUrl: string

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl
  }

  async chat(message: string): Promise<ChatResponse> {
    const response = await fetch(`${this.baseUrl}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message } satisfies ChatRequest),
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    return response.json() as Promise<ChatResponse>
  }

  async *chatStream(message: string) {
    const response = await fetch(`${this.baseUrl}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message } satisfies ChatRequest),
    })

    if (!response.ok || !response.body) {
      throw new Error(`Stream error: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      yield decoder.decode(value)
    }
  }

  getWebSocket(): WebSocket {
    const wsUrl = this.baseUrl.replace('http', 'ws') + '/ws'
    return new WebSocket(wsUrl)
  }
}

export const apiService = new ApiService()