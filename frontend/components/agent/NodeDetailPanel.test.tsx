// NodeDetailPanel.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { NodeDetailPanel } from './NodeDetailPanel'

jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

describe('NodeDetailPanel', () => {
  const baseStep = { id: 'step-1', title: 'Analyze', status: 'done', duration: 1.2, tokens: 340, detail: 'Classify & route task' }
  const baseNodeDef = { label: 'Node Label', description: 'Node description text' }
  const onClose = jest.fn()

  beforeEach(() => {
    onClose.mockClear()
  })

  it('renders nothing when nodeId is null', () => {
    const { container } = render(<NodeDetailPanel nodeId={null} step={baseStep} onClose={onClose} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when step is null', () => {
    const { container } = render(<NodeDetailPanel nodeId="step-1" step={null} onClose={onClose} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders step title', () => {
    render(<NodeDetailPanel nodeId="step-1" step={baseStep} onClose={onClose} />)
    expect(screen.getByText('Analyze')).toBeInTheDocument()
  })

  it('renders nodeDef label over step title when provided', () => {
    render(<NodeDetailPanel nodeId="step-1" step={baseStep} nodeDef={baseNodeDef} onClose={onClose} />)
    expect(screen.getByText('Node Label')).toBeInTheDocument()
  })

  it('renders status', () => {
    render(<NodeDetailPanel nodeId="step-1" step={baseStep} onClose={onClose} />)
    expect(screen.getByText('Completed')).toBeInTheDocument()
  })

  it('renders duration when present', () => {
    render(<NodeDetailPanel nodeId="step-1" step={baseStep} onClose={onClose} />)
    expect(screen.getByText(/1\.2s/)).toBeInTheDocument()
  })

  it('renders tokens when present', () => {
    render(<NodeDetailPanel nodeId="step-1" step={baseStep} onClose={onClose} />)
    expect(screen.getByText(/340/)).toBeInTheDocument()
  })

  it('renders detail when present', () => {
    render(<NodeDetailPanel nodeId="step-1" step={baseStep} onClose={onClose} />)
    expect(screen.getByText('Classify & route task')).toBeInTheDocument()
  })

  it('renders description when nodeDef is provided', () => {
    render(<NodeDetailPanel nodeId="step-1" step={baseStep} nodeDef={baseNodeDef} onClose={onClose} />)
    expect(screen.getByText('Node description text')).toBeInTheDocument()
  })

  it('renders close button and calls onClose when clicked', () => {
    render(<NodeDetailPanel nodeId="step-1" step={baseStep} onClose={onClose} />)
    fireEvent.click(screen.getByLabelText('Close detail panel'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('shows Running status for active steps', () => {
    const activeStep = { ...baseStep, status: 'active' }
    render(<NodeDetailPanel nodeId="step-1" step={activeStep} onClose={onClose} />)
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('shows Failed status for error steps', () => {
    const errorStep = { ...baseStep, status: 'error' }
    render(<NodeDetailPanel nodeId="step-1" step={errorStep} onClose={onClose} />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('formats tokens as 1k when >= 1000', () => {
    const stepManyTokens = { ...baseStep, tokens: 1500 }
    render(<NodeDetailPanel nodeId="step-1" step={stepManyTokens} onClose={onClose} />)
    expect(screen.getByText(/1\.5k/)).toBeInTheDocument()
  })
})
