// services/canvasWebSocket.ts
// WebSocket service for real-time Agent Canvas sync — step updates, approval, run completion
import { useAgentCanvasStore } from '@/lib/stores/agentCanvasStore'
import { useCanvasActions } from '@/lib/stores/useCanvasActions'

let socket: WebSocket | null = null
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

// ── Send ───────────────────────────────────────────────────────────────

export function sendCanvasMessage(payload: Record<string, unknown>): void {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload))
  }
}

// ── Connect ────────────────────────────────────────────────────────────

export function connectCanvasWebSocket(sessionId?: string): WebSocket {
  if (socket?.readyState === WebSocket.OPEN) return socket

  const params = sessionId ? `?session_id=${sessionId}` : ''
  const wsUrl = `ws://localhost:8000/ws${params}`

  socket = new WebSocket(wsUrl)

  socket.onopen = () => {
    console.log('[CanvasWS] Connected')
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleCanvasMessage(data)
    } catch (e) {
      console.error('[CanvasWS] Parse error:', e)
    }
  }

  socket.onclose = () => {
    console.warn('[CanvasWS] Disconnected — reconnecting in 2s')
    reconnectTimeout = setTimeout(() => {
      connectCanvasWebSocket(sessionId)
    }, 2000)
  }

  socket.onerror = (error) => {
    console.error('[CanvasWS] Error:', error)
  }

  return socket
}

// ── Message handler ────────────────────────────────────────────────────

function handleCanvasMessage(data: any): void {
  const canvasStore = useAgentCanvasStore.getState()

  switch (data.type) {
    case 'step':
      canvasStore.updateStep(data.step.name, {
        status: data.step.status,
        modelUsed: data.step.model_used,
        durationMs: data.step.duration_ms,
        tokens: data.step.tokens,
        error: data.step.error,
      })
      break

    case 'step_update':
      canvasStore.updateStep(data.name, {
        status: data.status,
        ...(data.metadata || {}),
      })
      break

    case 'approval_required':
      canvasStore.setApprovalStatus('PENDING', data.reason)
      break

    case 'execution_approved':
      canvasStore.setApprovalStatus('APPROVED')
      break

    case 'execution_rejected':
      canvasStore.setApprovalStatus('REJECTED', data.reason)
      break

    case 'run_complete':
      canvasStore.setRunning(false)
      break

    case 'run_start':
      canvasStore.setRunning(true)
      if (data.run_id) canvasStore.set({ runId: data.run_id })
      if (data.session_id) canvasStore.set({ sessionId: data.session_id })
      break

    case 'error':
      console.error('[CanvasWS] Agent error:', data.message)
      break

    default:
      break
  }
}

// ── React hook ─────────────────────────────────────────────────────────

import { useEffect } from 'react'

export const useCanvasWebSocket = (sessionId?: string) => {
  useEffect(() => {
    const ws = connectCanvasWebSocket(sessionId)
    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
      socket = null
    }
    // Intentional: reconnect only when sessionId changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])
}

// ── Approval helpers (for use outside React) ───────────────────────────

export function sendApprovalDecision(
  decision: 'APPROVED' | 'REJECTED',
  reason?: string,
): void {
  sendCanvasMessage({
    type: 'execute_decision',
    decision,
    reason,
    message_id: Date.now().toString(),
  })
}

export function disconnectCanvasWebSocket(): void {
  if (reconnectTimeout) clearTimeout(reconnectTimeout)
  socket?.close()
  socket = null
}
