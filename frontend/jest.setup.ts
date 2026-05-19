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
import { TextEncoder, TextDecoder } from 'util'

// Polyfill pour TextEncoder/TextDecoder requis par jsdom
TextEncoder.prototype.encode = TextEncoder.prototype.encode.bind(TextEncoder.prototype) // @ts-ignore
TextDecoder.prototype.decode = TextDecoder.prototype.decode.bind(TextDecoder.prototype) // @ts-ignore

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
const MockWebSocket = class {
  readyState = 3 // CONNECTING
  onopen = null
  onmessage = null
  onerror = null
  onclose = null

  send(data: string) {
    console.log('WebSocket send:', data)
  }

  close() {
    this.readyState = 4 // CLOSED
  }
}

(global as any).WebSocket = MockWebSocket

// Configure process.env pour les tests
process.env.NODE_ENV = 'test'

// Configure React strict mode
if (typeof window !== 'undefined') {
  // Assurez-vous que React fonctionne dans l'environnement de test
  const react = require('react')
  // React 18+ utilise son propre mécanisme de strict mode
}