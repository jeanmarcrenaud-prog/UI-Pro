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
  private currentContent = ''  // Source of truth for accumulated response
  private currentMessageContent = ''  // Input message (for reconnect)
  private flushTimeout: ReturnType<typeof setTimeout> | null = null
  private buffer = ''  // Buffer for UI flush only
  private heartbeat: ReturnType<typeof setInterval> | null = null
  private currentMessageId: string | null = null
  private reconnectAttempts = 0
  private _hasStartedStreaming = false

  // Centralized timer cleanup
  private clearTimers() {
    if (this.heartbeat) {
      clearInterval(this.heartbeat)
      this.heartbeat = null
    }
    if (this.flushTimeout) {
      clearTimeout(this.flushTimeout)
      this.flushTimeout = null
    }
  }

  // Reset stream state before reconnect resend
  private resetStreamState() {
    this._hasStartedStreaming = false
    this.buffer = ''
    this.currentContent = ''
  }

  // Clear message queue
  private clearQueue() {
    _messageQueue.length = 0
  }

  // Process queued messages
  private flushQueue() {
    while (_messageQueue.length > 0 && _ws?.readyState === WebSocket.OPEN) {
      const msg = _messageQueue.shift()
      if (msg) _ws.send(msg)
    }
  }

  // Queue message for delivery (now includes message_id)
  private queueOrSend(content: string) {
    const selectedModel = useUIStore.getState().selectedModel
    const payload = JSON.stringify({
      message_id: this.currentMessageId,
      message: content,
      model: selectedModel
    })
    
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

  // Attach handlers to WebSocket (reusable for initial + reconnect)
  private attachHandlers(ws: WebSocket, content: string) {
    ws.onopen = () => {
      _isConnected = true
      // Reset reconnect attempts on successful connection
      this.reconnectAttempts = 0
      events.emit('status', { status: 'connecting' })
      this.currentMessageContent = content
      this.queueOrSend(content)
      this.flushQueue()
      
      // Clear any existing heartbeat and start new one
      if (this.heartbeat) clearInterval(this.heartbeat)
      this.heartbeat = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        } else {
          this.clearTimers()
        }
      }, 15000)
    }

    ws.onmessage = (event) => {
      const data = event.data
      if (!data || !data.trim()) return
      
      try {
        const parsed = JSON.parse(data)
        
        // Ignore pong responses
        if (parsed.type === 'pong') {
          return
        }
        
        // Filter old messages by message_id
        if (parsed.message_id && parsed.message_id !== this.currentMessageId) {
          console.log('[ChatService] Ignoring old message:', parsed.message_id)
          return
        }
        
        // First token: switch from connecting to streaming
        if (parsed.type === 'token' || parsed.content) {
          if (!this._hasStartedStreaming) {
            this._hasStartedStreaming = true
            events.emit('status', { status: 'streaming' })
          }
        }
        
        // DONE - response complete
        if (parsed.done === true || parsed.type === 'done') {
          // Flush remaining buffer to UI (DO NOT add to currentContent - it's already there)
          if (this.buffer) {
            this.emitToHandlers({
              id: generateId(),
              role: 'assistant',
              content: this.buffer,
              status: 'streaming',
            })
            this.buffer = ''
          }
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
          events.emit('status', { status: 'error' })
          return
        }
        
        // TOKEN - streaming content extraction with buffering for smooth UX
        // Buffer for UI flush ONLY, currentContent is source of truth
        const text = parsed.content
        if (text && typeof text === 'string') {
          this.currentContent += text  // Source of truth
          this.buffer += text  // For UI flush
          
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

    // Just log errors, let onclose handle reconnection
    ws.onerror = () => {
      console.warn('[ChatService] WebSocket error')
    }

    ws.onclose = () => {
      _isConnected = false
      this.clearTimers()
      
      // Flush any pending buffer before reconnect (don't lose data)
      if (this.buffer) {
        this.emitToHandlers({
          id: generateId(),
          role: 'assistant',
          content: this.buffer,
          status: 'streaming',
        })
        this.buffer = ''
      }
      
      // Reconnect logic: max 3 attempts with exponential backoff
      if (this.currentMessageContent && this.reconnectAttempts < 3) {
        this.reconnectAttempts++
        events.emit('status', { status: 'reconnecting' })
        const delay = 500 * this.reconnectAttempts
        console.log(`[ChatService] Reconnect attempt ${this.reconnectAttempts}/3 in ${delay}ms`)
        
        setTimeout(() => {
          // Clear queue on reconnect to avoid double send
          this.clearQueue()
          // Reset stream state before resend to avoid duplication
          this.resetStreamState()
          
          // Create NEW WebSocket connection (old one is closed)
          const wsUrl = `ws://${window.location.hostname}:8000/ws`
          _ws = new WebSocket(wsUrl)
          
          // Attach handlers to new WebSocket
          this.attachHandlers(_ws, this.currentMessageContent)
        }, delay)
      } else {
        // All reconnect attempts failed or no message to resend
        events.emit('status', { status: 'idle' })
        this.reconnectAttempts = 0
        this.currentMessageContent = ''
        console.log('[ChatService] Reconnect failed, falling back to fetchFallback')
      }
    }
  }

  // Clean singleton connection
  disconnect() {
    this.clearTimers()
    // Reset state
    this.buffer = ''
    this.currentContent = ''
    this.currentMessageContent = ''
    this.currentMessageId = null
    
    if (_ws) {
      _ws.close()
      _ws = null
      _isConnected = false
    }
  }

  // Cancel in-progress stream
  cancel() {
    if (_ws?.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({
        type: 'cancel',
        message_id: this.currentMessageId
      }))
    }
    this.disconnect()
    events.emit('status', { status: 'idle' })
  }

  async sendMessage(content: string): Promise<void> {
    const selectedModel = useUIStore.getState().selectedModel
    console.log('[ChatService] 📤 sendMessage:', content.substring(0, 30))
    
    // Prevent sending while message is in progress
    if (this._hasStartedStreaming || this.currentMessageContent) {
      console.warn('[ChatService] Message in progress, ignoring new send')
      return
    }
    
    // Generate unique message ID for tracking
    const messageId = generateId()
    this.currentMessageId = messageId
    this.currentContent = ''
    this.currentMessageContent = ''
    this._hasStartedStreaming = false
    
    // Reuse existing WebSocket if connected
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({ message_id: messageId, message: content, model: selectedModel }))
      return
    }
    
    // Close stale connection
    this.disconnect()
    
    // Create SINGLE WebSocket connection
    const wsUrl = `ws://${window.location.hostname}:8000/ws`
    _ws = new WebSocket(wsUrl)
    
    // Attach all handlers
    this.attachHandlers(_ws, content)
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
        id: generateId(),
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