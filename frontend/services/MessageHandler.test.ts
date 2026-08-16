// MessageHandler.test.ts
// Role: Unit tests for MessageHandler - tool call event handling (Phase 1 unified events)

import { MessageHandler } from './MessageHandler'
import { events } from '@/lib/events'
import { debugLogger } from '@/lib/debug/logger'

jest.mock('@/lib/events', () => ({
  events: {
    emit: jest.fn(),
  },
}))

jest.mock('@/lib/debug/logger', () => ({
  debugLogger: {
    logTool: jest.fn(),
    logInfo: jest.fn(),
    logError: jest.fn(),
    logToken: jest.fn(),
    logStep: jest.fn(),
  },
}))

describe('MessageHandler', () => {
  const onToken = jest.fn()
  const onStep = jest.fn()
  const onError = jest.fn()
  const onComplete = jest.fn()

  let handler: MessageHandler

  beforeEach(() => {
    jest.clearAllMocks()
    handler = new MessageHandler(onToken, onStep, onError, onComplete)
  })

  describe('tool events', () => {
    it('should emit toolCall and toolResult for a tool message', () => {
      const msg = {
        type: 'tool',
        step_id: 'tool-write_file',
        title: 'Write File',
        content: '{"success": true, "output": "Created main.py"}',
      }
      handler.process(msg, null)

      expect(events.emit).toHaveBeenCalledWith('toolCall', { tool: 'write_file', status: 'done' })
      expect(events.emit).toHaveBeenCalledWith('toolResult', {
        tool: 'write_file',
        result: '{"success": true, "output": "Created main.py"}',
      })
      expect(debugLogger.logTool).toHaveBeenCalledWith('write_file', msg.content)
    })

    it('should not emit toolResult when content is empty', () => {
      const msg = { type: 'tool', step_id: 'tool-read_file', title: 'Read File', content: '' }
      handler.process(msg, null)

      expect(events.emit).toHaveBeenCalledWith('toolCall', { tool: 'read_file', status: 'done' })
      expect(events.emit).not.toHaveBeenCalledWith('toolResult', expect.anything())
    })

    it('should fall back to title when step_id is missing', () => {
      const msg = { type: 'tool', title: 'Execute Intent', content: 'done' }
      handler.process(msg, null)

      expect(events.emit).toHaveBeenCalledWith('toolCall', { tool: 'Execute Intent', status: 'done' })
    })

    it('should not forward tool events to token/step callbacks', () => {
      const msg = { type: 'tool', step_id: 'tool-write_file', title: 'Write File', content: 'ok' }
      handler.process(msg, null)

      expect(onToken).not.toHaveBeenCalled()
      expect(onStep).not.toHaveBeenCalled()
      expect(onComplete).not.toHaveBeenCalled()
    })
  })
})