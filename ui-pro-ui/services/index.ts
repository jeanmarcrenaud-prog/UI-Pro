// services/index.ts
// Role: Barrel exports for all service modules - exposes WebSocket chatService and modelDiscovery
// singleton services, with deprecated service references kept for backward compatibility

// Services index
// NOTE: Use chatService for WebSocket communication (singleton pattern)
export { chatService } from './chatService'
export { modelDiscovery } from './modelDiscovery'

// DEPRECATED - kept for reference only:
// export { agentService } from './agentService' // Use useAgentStore instead
// export { streamService } from './streamService' // Use chatService instead