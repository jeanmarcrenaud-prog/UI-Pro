// Agent Service - Business logic for agent orchestration
import type { AgentStep } from '@/lib/types'

type StepHandler = (steps: AgentStep[]) => void

interface AgentConfig {
  maxIterations: number
  streamingEnabled: boolean
}

const defaultConfig: AgentConfig = {
  maxIterations: 10,
  streamingEnabled: true,
}

class AgentService {
  private steps: AgentStep[] = []
  private stepHandler: StepHandler | null = null
  private config: AgentConfig
  private isActive: boolean = false

  constructor(config: Partial<AgentConfig> = {}) {
    this.config = { ...defaultConfig, ...config }
  }

  onSteps(handler: StepHandler) {
    this.stepHandler = handler
  }

  start(goal: string): void {
    this.isActive = true
    this.steps = [
      { id: '1', title: 'Analyzing request', status: 'active' },
      { id: '2', title: 'Planning solution', status: 'pending' },
      { id: '3', title: 'Executing', status: 'pending' },
      { id: '4', title: 'Reviewing', status: 'pending' },
    ]
    this.notify()
  }

  updateStep(stepId: string, status: AgentStep['status'], detail?: string): void {
    const step = this.steps.find((s) => s.id === stepId)
    if (step) {
      step.status = status
      if (detail) step.detail = detail
      this.notify()
    }
  }

  completeStep(stepId: string): void {
    this.updateStep(stepId, 'done')
    // Activate next step
    const idx = this.steps.findIndex((s) => s.id === stepId)
    if (idx >= 0 && idx < this.steps.length - 1) {
      this.steps[idx + 1].status = 'active'
      this.notify()
    }
  }

  fail(error: string): void {
    const activeStep = this.steps.find((s) => s.status === 'active')
    if (activeStep) {
      activeStep.status = 'error'
    }
    this.notify()
  }

  reset(): void {
    this.steps = []
    this.isActive = false
    this.notify()
  }

  getSteps(): AgentStep[] {
    return [...this.steps]
  }

  getIsActive(): boolean {
    return this.isActive
  }

  private notify() {
    this.stepHandler?.(this.steps)
  }
}

export const agentService = new AgentService()