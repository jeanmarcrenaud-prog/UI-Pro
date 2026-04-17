// API Service - WebSocket + REST fallback
import { events } from '@/lib/events'
import { useUIStore } from '@/lib/stores/uiStore'

// Event types for type safety
export const LogEvents = {
  LOG: 'log',
  STEP: 'step',
  TOOL: 'tool',
  TOKEN: 'token',
  DONE: 'done',
  ERROR: 'error',
} as const

export interface ChatRequest {
  message: string
  model?: string
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
      
      // Parse and detect log events from backend
      try {
        const parsed = JSON.parse(raw)
        const type = parsed.type || parsed.status || 'unknown'
        
        // Emit log events for debugging
        if (type === 'step' || type === 'tool') {
          events.emit(LogEvents.STEP, { 
            stepId: parsed.step_id || parsed.stepId,
            data: parsed.data || parsed.title,
            status: parsed.status 
          })
          // Also emit general log
          events.emit(LogEvents.LOG, { 
            message: `[${type.toUpperCase()}] ${parsed.data || parsed.title}`,
            type 
          })
        } else if (type === 'token') {
          events.emit(LogEvents.TOKEN, { data: parsed.data })
        } else if (type === 'error') {
          events.emit(LogEvents.ERROR, { error: parsed.error })
          events.emit(LogEvents.LOG, { 
            message: `[ERROR] ${parsed.error}`,
            type: 'error'
          })
        } else if (type === 'done') {
          events.emit(LogEvents.DONE, { data: parsed.data })
        }
      } catch {
        // Not JSON - emit as message
        events.emit('message', { data: raw })
      }
      
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
  // Get selected model from store
  const selectedModel = useUIStore.getState().selectedModel
  console.log('[Frontend] Sending with model:', selectedModel)
  
  // Try WebSocket first
  const wsService = await apiService()
  
  if (wsService && wsService.ws) {
    // Send via WebSocket with model
    const payload = { message, model: selectedModel }
    console.log('[Frontend] Sending JSON:', JSON.stringify(payload))
    wsService.ws.send(JSON.stringify(payload))
    
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
