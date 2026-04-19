// Chat Service - SINGLE WebSocket connection (singleton pattern)
// ==========================================================

import type { Message } from '@/lib/types'
import { useUIStore } from '@/lib/stores/uiStore'
import { events } from '@/lib/events'

type MessageHandler = (message: Message) => void

// Generate unique IDs (collision-free)
function generateId(): string {
  return crypto.randomUUID()
}

// SINGLETON - one WebSocket for all connections
let _ws: WebSocket | null = null
let _isConnected = false
let _messageHandlers: Set<MessageHandler> = new Set()
let _messageQueue: string[] = [] // Queue for rapid messages

class ChatService {
  private currentContent = ''
  private flushTimeout: NodeJS.Timeout | null = null
  private buffer = ''

  // Process queued messages
  private flushQueue() {
    while (_messageQueue.length > 0 && _ws?.readyState === WebSocket.OPEN) {
      const msg = _messageQueue.shift()
      if (msg) _ws.send(msg)
    }
  }

  // Queue message for delivery
  private queueOrSend(content: string) {
    const selectedModel = useUIStore.getState().selectedModel
    const payload = JSON.stringify({ message: content, model: selectedModel })
    
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(payload)
    } else {
      _messageQueue.push(payload) // Queue for later
    }
  }

  // Support multiple handlers (no overwrite!)
  onMessage(handler: MessageHandler) {
    _messageHandlers.add(handler)
    return () => _messageHandlers.delete(handler) // Return cleanup fn
  }
  
  private emitToHandlers(msg: Message) {
    _messageHandlers.forEach(h => h(msg))
  }

  // Clean singleton connection
  disconnect() {
    if (_ws) {
      _ws.close()
      _ws = null
      _isConnected = false
    }
  }

  async sendMessage(content: string): Promise<void> {
    const selectedModel = useUIStore.getState().selectedModel
    console.log('[ChatService] 📤 sendMessage:', content.substring(0, 30))
    
    this.currentContent = ''
    
    // Reuse existing WebSocket if connected
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({ message: content, model: selectedModel }))
      return
    }
    
    // Close stale connection
    this.disconnect()
    
    // Create SINGLE WebSocket connection
    const wsUrl = `ws://${window.location.hostname}:8000/ws`
    _ws = new WebSocket(wsUrl)
    
    _ws.onopen = () => {
      _isConnected = true
      events.emit('status', { status: 'streaming' })
      this.queueOrSend(content)
      this.flushQueue()
      
      // Heartbeat: ping every 15 seconds to detect dead connections
      const heartbeat = setInterval(() => {
        if (_ws?.readyState === WebSocket.OPEN) {
          _ws.send(JSON.stringify({ type: 'ping' }))
        } else {
          clearInterval(heartbeat)
        }
      }, 15000)
    }

_ws.onmessage = (event) => {
      const data = event.data
      if (!data || !data.trim()) return
      
      try {
        const parsed = JSON.parse(data)
        
        // DONE - response complete
        if (parsed.done === true || parsed.type === 'done') {
          this.emitToHandlers({
            id: generateId(),
            role: 'assistant',
            content: this.currentContent,
            status: 'done',
          })
          events.emit('status', { status: 'idle' })
          return
        }
        
        // STEP - emit step event
        if (parsed.type === 'step' || parsed.step_id || parsed.step) {
          const stepId = parsed.step_id || parsed.step || 'unknown'
          const status = parsed.status || 'active'
          events.emit('agentStep', { stepId, status })
          return
        }
        
        // ERROR - handle server errors
        if (parsed.type === 'error') {
          this.emitToHandlers({
            id: generateId(),
            role: 'assistant',
            content: parsed.message || 'Server error',
            status: 'error',
          })
          events.emit('status', { status: 'idle' })
          return
        }
        
        // TOKEN - streaming content extraction with buffering for smooth UX
        // PROPRE: ONLY use parsed.content (standardized format)
        const text = parsed.content
        if (text && typeof text === 'string') {
          this.currentContent += text
          this.buffer += text
          
          // Buffer and flush every 30ms for smooth streaming
          clearTimeout(this.flushTimeout || undefined)
          this.flushTimeout = setTimeout(() => {
            if (this.buffer) {
              this.emitToHandlers({
                id: generateId(),
                role: 'assistant',
                content: this.buffer,
                status: 'streaming',
              })
              this.buffer = ''
            }
          }, 30)
        }
      } catch (e) {
          // Skip JSON parse errors - don't display raw JSON
          console.warn('[ChatService] Parse error:', e)
        }
    }

    _ws.onerror = () => {
      this.disconnect()
      this.fetchFallback(content)
    }

    _ws.onclose = () => {
      _isConnected = false
      events.emit('status', { status: 'idle' })
    }
  }

  private async fetchFallback(content: string): Promise<void> {
    events.emit('status', { status: 'connecting' })
    const selectedModel = useUIStore.getState().selectedModel
    
    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content, model: selectedModel }),
      })
      const data = await response.json()
      
       this.emitToHandlers({
         id: generateId(),
         role: 'assistant',
         content: data.result || 'No response',
         status: data.status === 'error' ? 'error' : 'done',
       })
    } catch (error) {
      this.emitToHandlers({
        id: `generateId()`,
        role: 'assistant',
        content: error instanceof Error ? error.message : 'Connection failed',
        status: 'error',
      })
    }
    events.emit('status', { status: 'idle' })
  }
}

// SINGLETON instance
export const chatService = new ChatService()