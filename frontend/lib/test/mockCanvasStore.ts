// lib/test/mockCanvasStore.ts
// Test utilities for Agent Canvas — reset store, create mock steps, predefined pipeline scenarios
import { useAgentCanvasStore, type CanvasStep, type StepStatus } from '@/lib/stores/agentCanvasStore'

/** Reset the canvas store to empty + optionally inject test steps. */
export function resetCanvasStore(steps?: CanvasStep[]) {
  useAgentCanvasStore.getState().resetCanvas()
  if (steps && steps.length > 0) {
    useAgentCanvasStore.getState().setSteps(steps)
  }
}

/** Factory: create a single CanvasStep with sensible defaults. */
export function createMockStep(
  name: string,
  status: StepStatus = 'pending',
  overrides: Partial<CanvasStep> = {},
): CanvasStep {
  return { name, status, ...overrides }
}

// ── Predefined pipeline scenarios ────────────────────────────────────────

export const TestPipelines = {
  /** No steps — empty state */
  empty: [] as CanvasStep[],

  /** Full success pipeline (Analyze → Execute done) */
  fullSuccess: [
    createMockStep('step-analyzing', 'done', { durationMs: 1200, tokens: 340 }),
    createMockStep('step-planning', 'done', { durationMs: 3400, tokens: 890 }),
    createMockStep('step-coding', 'done', { durationMs: 8100, tokens: 2450 }),
    createMockStep('step-reviewing', 'done', { durationMs: 2100, tokens: 560 }),
    createMockStep('step-executing', 'done', { durationMs: 4500, tokens: 120 }),
  ],

  /** Mid-execution — Code is running */
  running: [
    createMockStep('step-analyzing', 'done', { durationMs: 1200, tokens: 340 }),
    createMockStep('step-planning', 'done', { durationMs: 3400, tokens: 890 }),
    createMockStep('step-coding', 'running', { durationMs: 5000, tokens: 1500 }),
  ],

  /** Pipeline with an error */
  withError: [
    createMockStep('step-analyzing', 'done', { durationMs: 1200, tokens: 340 }),
    createMockStep('step-planning', 'done', { durationMs: 3400, tokens: 890 }),
    createMockStep('step-coding', 'error', {
      durationMs: 12000,
      tokens: 5000,
      error: 'SyntaxError: unexpected token',
    }),
  ],

  /** Awaiting approval state */
  awaitingApproval: [
    createMockStep('step-analyzing', 'done', { durationMs: 1200, tokens: 340 }),
    createMockStep('step-planning', 'done', { durationMs: 3400, tokens: 890 }),
    createMockStep('step-coding', 'done', { durationMs: 8100, tokens: 2450 }),
    createMockStep('step-reviewing', 'done', { durationMs: 2100, tokens: 560 }),
    createMockStep('step-executing', 'awaiting_approval', {
      startedAt: new Date().toISOString(),
    }),
  ],
}
