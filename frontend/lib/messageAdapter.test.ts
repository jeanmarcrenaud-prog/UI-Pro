// messageAdapter.test.ts
// Role: Unit tests for normalizeMessage - covers duration/token extraction,
// type detection, content extraction, and edge cases

import { normalizeMessage, toStoreMessage } from './messageAdapter'

describe('normalizeMessage', () => {
  it('should return unknown type for null/undefined input', () => {
    expect(normalizeMessage(null)).toEqual({ type: 'unknown', content: '' })
    expect(normalizeMessage(undefined)).toEqual({ type: 'unknown', content: '' })
  })

  it('should extract duration from raw message', () => {
    const raw = {
      type: 'step',
      content: 'Analyzing request',
      duration: 2.5,
      step_id: 'step-analyzing',
    }
    const result = normalizeMessage(raw)
    expect(result.duration).toBe(2.5)
    expect(result.type).toBe('step')
  })

  it('should extract tokenCount from raw message', () => {
    const raw = {
      type: 'token',
      content: 'Hello world',
      token_count: 150,
    }
    const result = normalizeMessage(raw)
    expect(result.tokenCount).toBe(150)
  })

  it('should extract both duration and tokenCount', () => {
    const raw = {
      type: 'step',
      content: 'Planning solution',
      duration: 5.2,
      token_count: 2048,
      step_id: 'step-planning',
    }
    const result = normalizeMessage(raw)
    expect(result.duration).toBe(5.2)
    expect(result.tokenCount).toBe(2048)
    expect(result.type).toBe('step')
    expect(result.stepId).toBe('step-planning')
  })

  it('should handle camelCase tokenCount field', () => {
    const raw = {
      type: 'step',
      content: 'Reviewing code',
      tokenCount: 512,
    }
    const result = normalizeMessage(raw)
    expect(result.tokenCount).toBe(512)
  })

  it('should handle snake_case token_count field', () => {
    const raw = {
      type: 'step',
      content: 'Executing code',
      token_count: 1024,
    }
    const result = normalizeMessage(raw)
    expect(result.tokenCount).toBe(1024)
  })

  it('should handle missing duration/tokenCount gracefully', () => {
    const raw = {
      type: 'done',
      content: 'Task completed',
    }
    const result = normalizeMessage(raw)
    expect(result.duration).toBeUndefined()
    expect(result.tokenCount).toBeUndefined()
  })

  it('should detect token type from delta field', () => {
    const raw = {
      delta: 'Hello',
      status: 'streaming',
    }
    const result = normalizeMessage(raw)
    expect(result.type).toBe('token')
    expect(result.content).toBe('Hello')
  })

  it('should detect done type', () => {
    const raw = {
      done: true,
    }
    const result = normalizeMessage(raw)
    expect(result.type).toBe('done')
  })

  it('should detect error type', () => {
    const raw = {
      type: 'error',
      message: 'Something went wrong',
    }
    const result = normalizeMessage(raw)
    expect(result.type).toBe('error')
    expect(result.content).toBe('Something went wrong')
  })

  it('should normalize status values', () => {
    const raw = {
      type: 'step',
      status: 'active',
      step_status: 'done',
    }
    const result = normalizeMessage(raw)
    expect(result.status).toBe('active')
  })

  it('should handle tool type', () => {
    const raw = {
      type: 'tool',
      content: 'Tool result',
    }
    const result = normalizeMessage(raw)
    expect(result.type).toBe('tool')
  })

  it('should extract messageId from various field names', () => {
    expect(normalizeMessage({ message_id: 'abc' }).messageId).toBe('abc')
    expect(normalizeMessage({ id: 'def' }).messageId).toBe('def')
    expect(normalizeMessage({ messageId: 'ghi' }).messageId).toBe('ghi')
  })

  it('should extract stepId from various field names', () => {
    expect(normalizeMessage({ step_id: 'step-1' }).stepId).toBe('step-1')
    expect(normalizeMessage({ stepId: 'step-2' }).stepId).toBe('step-2')
  })

  it('should extract title from step_title field', () => {
    const raw = {
      type: 'step',
      step_title: 'My Step',
    }
    const result = normalizeMessage(raw)
    expect(result.title).toBe('My Step')
  })

  it('should handle code field', () => {
    const raw = {
      type: 'step',
      code: 'print("hello")',
    }
    const result = normalizeMessage(raw)
    expect(result.code).toBe('print("hello")')
  })

  it('should fallback to unknown for unrecognized formats', () => {
    const raw = { foo: 'bar' }
    const result = normalizeMessage(raw)
    expect(result.type).toBe('unknown')
    expect(result.content).toBe('')
  })
})

describe('toStoreMessage', () => {
  it('should convert normalized message to store message', () => {
    const normalized = {
      type: 'step' as const,
      content: 'Hello',
      messageId: 'msg-1',
      stepId: 'step-1',
      status: 'done' as const,
      duration: 1.5,
      tokenCount: 100,
    }
    const result = toStoreMessage(normalized, 'assistant-1')
    expect(result.id).toBe('msg-1')
    expect(result.role).toBe('assistant')
    expect(result.content).toBe('Hello')
    expect(result.delta).toBe('Hello')
    expect(result.status).toBe('done')
    expect(result.type).toBe('step')
    expect(result.step_id).toBe('step-1')
  })

  it('should fallback to assistantId when messageId is missing', () => {
    const normalized = {
      type: 'token' as const,
      content: 'Test',
    }
    const result = toStoreMessage(normalized, 'fallback-id')
    expect(result.id).toBe('fallback-id')
  })
})
