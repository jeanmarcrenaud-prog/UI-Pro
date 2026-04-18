// Chat Service - SINGLE WebSocket connection (singleton pattern)
// ==========================================================

import type { Message } from '@/lib/types'
import { useUIStore } from '@/lib/stores/uiStore'
import { events } from '@/lib/events'

type MessageHandler = (message: Message) => void

// SINGLETON - one WebSocket for all connections
let _ws: WebSocket | null = null
let _isConnected = false
let _messageHandlers: Set<MessageHandler> = new Set()

class ChatService {
  private currentContent = ''

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
      _ws?.send(JSON.stringify({ message: content, model: selectedModel }))
    }

    _ws.onmessage = (event) => {
      const data = event.data
      if (!data || !data.trim()) return
      
      try {
        const parsed = JSON.parse(data)
        
        // DONE - response complete
        if (parsed.type === 'done') {
          this.emitToHandlers({
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: this.currentContent,
            status: 'done',
          })
          events.emit('status', { status: 'idle' })
          return
        }
        
        // STEP - emit step event
        if (parsed.type === 'step') {
          events.emit('agentStep', { 
            stepId: parsed.step_id, 
            status: parsed.status
          })
          return
        }
        
        // TOKEN - streaming content
        const text = parsed.data || parsed.content || parsed.message || parsed.text || ''
        if (text) {
          this.currentContent += text
          this.emitToHandlers({
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: text,
            status: 'streaming',
          })
        }
      } catch {
        // Plain text fallback
        this.currentContent += data
        this.emitToHandlers({
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: data,
          status: 'streaming',
        })
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
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: data.result || 'No response',
        status: data.status === 'error' ? 'error' : 'done',
      })
    } catch (error) {
      this.emitToHandlers({
        id: `msg-${Date.now()}`,
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