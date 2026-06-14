// jest.setup.ts
// Role: Jest test environment setup - configures polyfills for TextEncoder/TextDecoder, mocks
// window.matchMedia and WebSocket, sets NODE_ENV, and initializes React testing library globals

// jest.setup.ts
// Role: Jest test environment setup - configures polyfills for TextEncoder/TextDecoder, mocks
// window.matchMedia and WebSocket, sets NODE_ENV, and initializes React testing library globals

/**
 * Setup file pour Jest - configure l'environnement de test
 */

// Import required test setup
import '@testing-library/jest-dom'

// Polyfill TextEncoder/TextDecoder only if NOT already available (jsdom provides native ones)
if (typeof TextEncoder === 'undefined') {
  const { TextEncoder: TE, TextDecoder: TD } = require('util')
  ;(global as any).TextEncoder = TE
  ;(global as any).TextDecoder = TD
}

// Mock pour window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true
  })
})

// Mock WebSocket pour les tests
function MockWebSocket(this: any) {
  this.readyState = 3 // CONNECTING
  this.onopen = null
  this.onmessage = null
  this.onerror = null
  this.onclose = null
}

MockWebSocket.prototype.send = function(data: string) {
  console.log('WebSocket send:', data)
}

MockWebSocket.prototype.close = function() {
  this.readyState = 4 // CLOSED
}

;(global as any).WebSocket = MockWebSocket

// Polyfill crypto.randomUUID for jsdom (used by useChatActions)
if (typeof crypto !== 'undefined' && !crypto.randomUUID) {
  (crypto as any).randomUUID = function() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c: string) {
      const r = Math.random() * 16 | 0
      const v = c === 'x' ? r : (r & 0x3 | 0x8)
      return v.toString(16)
    })
  }
}

// Configure process.env pour les tests
process.env.NODE_ENV = 'test'

// Configure React strict mode
if (typeof window !== 'undefined') {
  // Assurez-vous que React fonctionne dans l'environnement de test
  const react = require('react')
  // React 18+ utilise son propre mécanisme de strict mode
}