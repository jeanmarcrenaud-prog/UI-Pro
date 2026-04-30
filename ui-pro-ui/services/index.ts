// services/index.ts
// Role: Barrel exports for all service modules

// Core services
export { chatService } from './chatService'
export { modelDiscovery } from './modelDiscovery'

// Streaming service
export { streamService, createStreamService } from './streamService'
export type { StreamEvent, BackendStreamChunk, StreamOptions } from './streamService'