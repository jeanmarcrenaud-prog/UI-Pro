// services/FallbackHandler.ts
// SSE and REST fallback handlers with AbortController support

import type { FallbackParams, MessageHandlerCallback } from './types'
import { debugLogger } from '@/lib/debug/logger'

export class FallbackHandler {
  private currentAbort: AbortController | null = null

  async sendSSE(url: string, params: FallbackParams, onToken: MessageHandlerCallback): Promise<boolean> {
    this.cancel()
    this.currentAbort = new AbortController()
    const signal = this.currentAbort.signal

    debugLogger.logInfo(`SSE started: ${params.message?.slice(0, 30)}...`, 'sse')

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        signal,
      })

      if (!response.ok || !response.body) {
        debugLogger.logError('SSE response failed', { status: response.status })
        return false
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        if (signal.aborted) {
          reader.cancel()
          debugLogger.logInfo('SSE aborted', 'sse')
          return false
        }

        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              const content = data.content || data.token || ''
              const isDone = !!data.done
              
              if (content) {
                debugLogger.logToken(content, data.token_count)
                onToken(content, isDone)
              }
              
              if (isDone) {
                debugLogger.logInfo('SSE completed', 'sse')
              }
            } catch (err) {
              console.warn('[SSE] Parse error:', err)
            }
          }
        }
      }

      return true
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        console.log('[SSE] Aborted')
        return false
      }
      debugLogger.logError('SSE failed', err)
      console.warn('[SSE] Failed:', err)
      return false
    } finally {
      this.currentAbort = null
    }
  }

  async sendREST(url: string, params: FallbackParams): Promise<string> {
    this.cancel()
    this.currentAbort = new AbortController()

    debugLogger.logInfo(`REST started: ${params.message?.slice(0, 30)}...`, 'rest')

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        signal: this.currentAbort.signal,
      })
      const data = await response.json()
      const result = data?.result || data?.response || data?.message || ''
      debugLogger.logInfo(`REST completed: ${result.slice(0, 30)}...`, 'rest')
      return result
    } catch (err) {
      if ((err as Error).name === 'AbortError') return ''
      debugLogger.logError('REST failed', err)
      throw err
    } finally {
      this.currentAbort = null
    }
  }

  cancel(): void {
    this.currentAbort?.abort()
    this.currentAbort = null
  }
}