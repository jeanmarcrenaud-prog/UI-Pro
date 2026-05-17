// services/FallbackHandler.ts
// SSE and REST fallback handlers with AbortController support

import type { FallbackParams, MessageHandlerCallback } from './types'

export class FallbackHandler {
  private currentAbort: AbortController | null = null

  async sendSSE(url: string, params: FallbackParams, onToken: MessageHandlerCallback): Promise<boolean> {
    this.cancel()
    this.currentAbort = new AbortController()
    const signal = this.currentAbort.signal

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        signal,
      })

      if (!response.ok || !response.body) return false

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        if (signal.aborted) {
          reader.cancel()
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
              onToken(data.content || data.token || '', !!data.done)
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
      console.warn('[SSE] Failed:', err)
      return false
    } finally {
      this.currentAbort = null
    }
  }

  async sendREST(url: string, params: FallbackParams): Promise<string> {
    this.cancel()
    this.currentAbort = new AbortController()

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        signal: this.currentAbort.signal,
      })
      const data = await response.json()
      return data?.result || data?.response || data?.message || ''
    } catch (err) {
      if ((err as Error).name === 'AbortError') return ''
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