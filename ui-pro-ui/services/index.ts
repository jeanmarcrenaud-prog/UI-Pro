// Services index
// NOTE: Use chatService for WebSocket communication (singleton pattern)
export { chatService } from './chatService'
export { modelDiscovery } from './modelDiscovery'

// DEPRECATED - kept for reference only:
// export { agentService } from './agentService' // Use useAgentStore instead
// export { streamService } from './streamService' // Use chatService instead