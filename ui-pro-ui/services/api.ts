// API Service - WebSocket + REST fallback
import { events } from '@/lib/events'

export interface ChatRequest {
  message: string
}

export interface ChatResponse {
  result?: string
  error?: string
  text?: string
  code?: any
  files?: any
  status?: string
  type?: string
  step_id?: string
  title?: string
  content?: string
  status?: string
  delta?: string
  data?: string
}

const wsRef: WeakRef<WebSocket> | null = null

export async function apiService() {
  // Initialize WebSocket
  const wsUrl = `ws://${window.location.hostname}:8000/ws`
  
  try {
    const ws = new WebSocket(wsUrl)
    const wsFinal = ws
    
    wsFinal.onopen = () => {
      console.log('WebSocket connected to', wsUrl)
    }
    
    wsFinal.onmessage = (event) => {
      const raw = event.data
      if (!raw) return
      
      if (raw === '[DONE]') {
        if (wsFinal) {
          wsFinal.close()
          wsFinal = null
        }
        return
      }
      
      events.emit('message', { data: raw })
      events.emit('status', { data: raw })
    }
    
    wsFinal.onerror = () => {
      console.warn('WebSocket error, falling back to REST')
      if (wsFinal) {
        wsFinal.close()
        wsFinal = null
      }
    }
    
    wsFinal.onclose = () => {
      console.log('WebSocket closed')
      wsFinal = null
    }
    
    return { ws: wsFinal }
  } catch (error) {
    console.error('WebSocket failed, will use REST:', error)
    return null
  }
}

export async function chat(message: string): Promise<ChatResponse> {
  // Try WebSocket first
  const wsService = await apiService()
  
  if (wsService && wsService.ws) {
    // Send via WebSocket
    wsService.ws.send(JSON.stringify({ message }))
    
    // Wait for response
    return new Promise((resolve) => {
      // Store current message for matching
      const currentMsg = message
      let response: ChatResponse = {}
      
      // Listen for response (simplified - in production would use message IDs)
      setTimeout(() => {
        // If still connected, check for cached responses
        if (wsService.ws && wsService.ws.readyState === ws.CONNECTING) {
          resolve(response)
        }
      }, 100)
    })
  }
  
  // Fallback to REST API
  try {
    const response = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    return data
  } catch (error) {
    console.error('REST API failed:', error)
    throw error
  }
}
