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
  private streamTimeout: ReturnType<typeof setTimeout> | null = null  // Timeout for stalled streaming
  private streamStartTime = 0  // Track when streaming started
  private currentMessageId: string | null = null
  private reconnectAttempts = 0
  private _hasStartedStreaming = false
  private _lastChunkIndex = 0  // Track chunk order to prevent duplication
  private static readonly STREAM_TIMEOUT_MS = 30000  // 30s timeout for streaming

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
    if (this.streamTimeout) {
      clearTimeout(this.streamTimeout)
      this.streamTimeout = null
    }
  }

  // Start stream timeout - kill if no tokens for 30s
  private startStreamTimeout() {
    this.clearStreamTimeout()
    this.streamTimeout = setTimeout(() => {
      console.warn('[ChatService] Stream timeout - no response for 30s')
      this.handleStreamTimeout()
    }, ChatService.STREAM_TIMEOUT_MS)
  }

  private resetStreamTimeout() {
    // Don't reset if not connected
    if (!_isConnected) return
    if (this.streamTimeout) {
      clearTimeout(this.streamTimeout)
    }
    this.streamTimeout = setTimeout(() => {
      console.warn('[ChatService] Stream timeout - stalled')
      this.handleStreamTimeout()
    }, ChatService.STREAM_TIMEOUT_MS)
  }

  private clearStreamTimeout() {
    if (this.streamTimeout) {
      clearTimeout(this.streamTimeout)
      this.streamTimeout = null
    }
  }

  private handleStreamTimeout() {
    this.clearTimers()
    this.disconnect()
    // Emit retrying status before fallback
    if (this.currentMessageContent) {
      events.emit('status', { status: 'retrying' })
      console.log('[ChatService] Timeout - retrying with fetchFallback')
      this.fetchFallback(this.currentMessageContent)
    } else {
      events.emit('status', { status: 'error' })
    }
  }

  // Reset stream state before reconnect resend
  private resetStreamState() {
    this._hasStartedStreaming = false
    this.buffer = ''
    this.currentContent = ''
    this._lastChunkIndex = 0
  }

  // Attach message handler (reused on reconnect)
  private attachMessageHandler(ws: WebSocket) {
    ws.onmessage = (event) => {
      const data = event.data
      if (!data || !data.trim()) return
      
      try {
        const parsed = JSON.parse(data)
        
        // Ignore pong responses
        if (parsed.type === 'pong') {
          return
        }
        
        // Handle resume acknowledgment
        if (parsed.type === 'resume') {
          console.log('[ChatService] Resuming from chunk:', parsed.resuming_from)
          return
        }
        
        // Filter old messages by message_id
        if (parsed.message_id && parsed.message_id !== this.currentMessageId) {
          console.log('[ChatService] Ignoring old message:', parsed.message_id)
          return
        }
        
        // Filter duplicate chunks by chunk_index
        if (parsed.chunk_index && parsed.chunk_index <= this._lastChunkIndex) {
          console.log('[ChatService] Ignoring duplicate chunk:', parsed.chunk_index)
          return
        }
        if (parsed.chunk_index) {
          this._lastChunkIndex = parsed.chunk_index
        }
        
        // First token: switch from connecting to streaming
        if (parsed.type === 'token' || parsed.content) {
          if (!this._hasStartedStreaming) {
            this._hasStartedStreaming = true
            this.streamStartTime = Date.now()
            this.startStreamTimeout()
            events.emit('status', { status: 'streaming' })
          }
          this.resetStreamTimeout()
        }
        
        // DONE - response complete
        if (parsed.done === true || parsed.type === 'done') {
          this.clearStreamTimeout()
          if (this.buffer) {
            this.emitToHandlers({
              id: generateId(),
              role: 'assistant',
              content: this.buffer,
              status: 'streaming',
              message_id: this.currentMessageId || undefined,
            })
            this.buffer = ''
          }
          this.emitToHandlers({
            id: generateId(),
            role: 'assistant',
            content: this.currentContent,
            status: 'done',
            message_id: this.currentMessageId || undefined,
          })
          events.emit('status', { status: 'idle' })
          return
        }
        
        // STEP - emit step event
        if (parsed.type === 'step' || parsed.step_id || parsed.step) {
          this.resetStreamTimeout()
          const stepId = parsed.step_id || parsed.step || 'unknown'
          const status = parsed.status || 'active'
          events.emit('agentStep', { stepId, status })
          return
        }
        
        // ERROR - handle server errors
        if (parsed.type === 'error') {
          this.clearStreamTimeout()
          this.emitToHandlers({
            id: generateId(),
            role: 'assistant',
            content: parsed.message || 'Server error',
            status: 'error',
            message_id: this.currentMessageId || undefined,
          })
          events.emit('status', { status: 'error' })
          return
        }
        
        // TOKEN - streaming content (handle both response and thinking fields)
        const text = parsed.content || parsed.thinking
        if (text && typeof text === 'string') {
          this.currentContent += text
          this.buffer += text
          
          clearTimeout(this.flushTimeout || undefined)
          this.flushTimeout = setTimeout(() => {
            if (this.buffer) {
              this.emitToHandlers({
                id: generateId(),
                role: 'assistant',
                content: this.buffer,
                status: 'streaming',
                message_id: this.currentMessageId || undefined,
              })
              this.buffer = ''
            }
          }, 30)
        }
      } catch (e) {
        console.warn('[ChatService] Parse error:', e)
      }
    }
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

    // Reuse message handler
    this.attachMessageHandler(ws)
    
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
          message_id: this.currentMessageId || undefined,
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
          // Reset stream state but preserve last chunk index for resume
          this._hasStartedStreaming = false
          this.buffer = ''
          
          // Create NEW WebSocket connection (old one is closed)
          const selectedModel = useUIStore.getState().selectedModel
          const wsUrl = `ws://${window.location.hostname}:8000/ws`
          _ws = new WebSocket(wsUrl)
          
          // Send message with last_chunk_index for resume
          const resumePayload = JSON.stringify({
            message_id: this.currentMessageId,
            message: this.currentMessageContent,
            model: selectedModel,
            last_chunk_index: this._lastChunkIndex
          })
          
          _ws.onopen = () => {
            _isConnected = true
            this.reconnectAttempts = 0
            events.emit('status', { status: 'connecting' })
            
            // Send resume message only (not queue - avoids double send)
            _ws?.send(resumePayload)
            
            // Start heartbeat
            if (this.heartbeat) clearInterval(this.heartbeat)
            this.heartbeat = setInterval(() => {
              if (_ws?.readyState === WebSocket.OPEN) {
                _ws.send(JSON.stringify({ type: 'ping' }))
              } else {
                this.clearTimers()
              }
            }, 15000)
          }
          
          // Re-attach message handler
          this.attachMessageHandler(_ws)
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

  async sendMessage(content: string, messageId?: string): Promise<void> {
    const selectedModel = useUIStore.getState().selectedModel
    console.log('[ChatService] 📤 sendMessage:', content.substring(0, 30))
    
    // Prevent sending while message is in progress
    if (this._hasStartedStreaming || this.currentMessageContent) {
      console.warn('[ChatService] Message in progress, ignoring new send')
      return
    }
    
    // Use provided messageId or generate new one
    this.currentMessageId = messageId || generateId()
    this.currentContent = ''
    this.currentMessageContent = ''
    this._hasStartedStreaming = false
    this._lastChunkIndex = 0
    
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