// services/index.ts
// Role: Barrel exports for all service modules

// Core services
export { chatService } from './chatService'
export { modelDiscovery } from './modelDiscovery'

// Streaming service
export { streamService } from './streamService'
export type { StreamService, StreamServiceOptions, BackendStreamChunk, StreamEvent } from './streamService'