// services/constants.ts
// Centralized constants for chat service

export const WS_EVENTS = {
  PING: 'ping',
  PONG: 'pong',
  CANCEL: 'cancel',
  RESUME_ACK: 'resume_ack',
  STEP: 'step',
  ERROR: 'error',
  DONE: 'done',
} as const

export const RECONNECT = {
  MAX_ATTEMPTS: 5,
  BASE_DELAY: 1000,
  MAX_DELAY: 10000,
  BACKOFF_FACTOR: 1.5,
} as const

export const HEARTBEAT_INTERVAL = 30000 // 30s

export const CONNECTION_TIMEOUT = 8000 // 8s

export const REQUEST_TIMEOUT = 30000 // 30s max wait for concurrent requests

export const DEFAULT_MODEL = 'qwen3.6:latest'
export const DEFAULT_PROVIDER = 'ollama'

export const MAX_HANDLERS = 10