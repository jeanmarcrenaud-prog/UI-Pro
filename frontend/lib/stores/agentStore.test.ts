// agentStore.test.ts
// Role: Unit tests for agentStore - covers updateStep, addStep, setStep,
// reset, start, and getActiveStep with focus on duration/tokens tracking

import { useAgentStore } from './agentStore'

describe('agentStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    useAgentStore.getState().reset()
  })

  describe('updateStep', () => {
    it('should add a new step when id does not exist', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-analyzing', 'active', 'Analyzing...', 1.5, 100)

      const steps = useAgentStore.getState().steps
      expect(steps).toHaveLength(1)
      expect(steps[0]).toMatchObject({
        id: 'step-analyzing',
        title: 'analyzing',
        status: 'active',
        detail: 'Analyzing...',
        duration: 1.5,
        tokens: 100,
      })
    })

    it('should update existing step status', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-analyzing', 'active')
      store.updateStep('step-analyzing', 'done')

      const steps = useAgentStore.getState().steps
      expect(steps[0].status).toBe('done')
    })

    it('should update step duration and tokens', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-planning', 'active')
      store.updateStep('step-planning', 'done', 'Completed', 3.2, 500)

      const step = useAgentStore.getState().steps[0]
      expect(step.duration).toBe(3.2)
      expect(step.tokens).toBe(500)
      expect(step.status).toBe('done')
    })

    it('should allow reactivation from done to active (fix loop)', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-coding', 'active')
      store.updateStep('step-coding', 'done')
      store.updateStep('step-coding', 'active') // Now allowed for fix loop

      const step = useAgentStore.getState().steps[0]
      expect(step.status).toBe('active') // Fix loop re-enters code node
    })

    it('should allow done to done transition', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-reviewing', 'done')
      store.updateStep('step-reviewing', 'done', 'Final review')

      const step = useAgentStore.getState().steps[0]
      expect(step.status).toBe('done')
      expect(step.detail).toBe('Final review')
    })

    it('should preserve existing duration/tokens when not provided', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-executing', 'active', 'Running', 5.0, 1000)
      store.updateStep('step-executing', 'done')

      const step = useAgentStore.getState().steps[0]
      expect(step.duration).toBe(5.0)
      expect(step.tokens).toBe(1000)
    })

    it('should update currentStepId and currentStep index', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-analyzing', 'active')

      const state = useAgentStore.getState()
      expect(state.currentStepId).toBe('step-analyzing')
      expect(state.currentStep).toBe(0)
    })

    it('should handle multiple steps', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-analyzing', 'done', '', 1.0, 50)
      store.updateStep('step-planning', 'active', '', 2.0, 100)

      const steps = useAgentStore.getState().steps
      expect(steps).toHaveLength(2)
      expect(steps[0].status).toBe('done')
      expect(steps[1].status).toBe('active')
    })

    it('should format title from id', () => {
      const store = useAgentStore.getState()
      store.updateStep('step-my-task', 'pending')

      const step = useAgentStore.getState().steps[0]
      expect(step.title).toBe('my task')
    })
  })

  describe('addStep', () => {
    it('should add a step to the end of the list', () => {
      const store = useAgentStore.getState()
      store.addStep({
        id: 'step-1',
        title: 'Step 1',
        status: 'pending',
        duration: 1.0,
        tokens: 50,
      })

      const steps = useAgentStore.getState().steps
      expect(steps).toHaveLength(1)
      expect(steps[0].title).toBe('Step 1')
    })
  })

  describe('setStep', () => {
    it('should replace step at specific index', () => {
      const store = useAgentStore.getState()
      store.addStep({ id: 'step-1', title: 'Old', status: 'pending' })
      store.setStep({ id: 'step-1', title: 'New', status: 'active' }, 0)

      const steps = useAgentStore.getState().steps
      expect(steps[0].title).toBe('New')
      expect(steps[0].status).toBe('active')
    })
  })

  describe('setSteps', () => {
    it('should replace all steps and reset currentStep', () => {
      const store = useAgentStore.getState()
      store.addStep({ id: 'step-1', title: 'Step 1', status: 'pending' })
      store.setSteps([
        { id: 'step-a', title: 'A', status: 'active' },
        { id: 'step-b', title: 'B', status: 'pending' },
      ])

      const state = useAgentStore.getState()
      expect(state.steps).toHaveLength(2)
      expect(state.currentStep).toBe(0)
      expect(state.currentStepId).toBe('step-a')
    })
  })

  describe('reset', () => {
    it('should clear all state', () => {
      const store = useAgentStore.getState()
      store.addStep({ id: 'step-1', title: 'Step', status: 'active' })
      store.reset()

      const state = useAgentStore.getState()
      expect(state.steps).toHaveLength(0)
      expect(state.isActive).toBe(false)
      expect(state.currentStep).toBe(0)
      expect(state.currentStepId).toBeUndefined()
    })
  })

  describe('start', () => {
    it('should set isActive and initialize steps', () => {
      const store = useAgentStore.getState()
      store.start([
        { id: 'step-1', title: 'Step 1', status: 'pending' },
        { id: 'step-2', title: 'Step 2', status: 'active' },
      ])

      const state = useAgentStore.getState()
      expect(state.isActive).toBe(true)
      expect(state.steps).toHaveLength(2)
      expect(state.currentStepId).toBe('step-2')
    })
  })

  describe('getActiveStep', () => {
    it('should return the active step', () => {
      const store = useAgentStore.getState()
      store.start([
        { id: 'step-1', title: 'Step 1', status: 'pending' },
        { id: 'step-2', title: 'Step 2', status: 'active' },
      ])

      const activeStep = useAgentStore.getState().getActiveStep()
      expect(activeStep).toBeDefined()
      expect(activeStep?.id).toBe('step-2')
    })

    it('should return undefined when no active step', () => {
      const store = useAgentStore.getState()
      store.start([
        { id: 'step-1', title: 'Step 1', status: 'done' },
      ])

      const activeStep = useAgentStore.getState().getActiveStep()
      expect(activeStep).toBeUndefined()
    })
  })
})
