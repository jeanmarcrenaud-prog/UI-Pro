// NodePalette.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { NodePalette } from './NodePalette'

describe('NodePalette', () => {
  it('renders nothing when closed', () => {
    const { container } = render(<NodePalette isOpen={false} onClose={jest.fn()} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders palette nodes when open', () => {
    render(<NodePalette isOpen={true} onClose={jest.fn()} />)
    expect(screen.getByText('Analyze')).toBeInTheDocument()
    expect(screen.getByText('Plan')).toBeInTheDocument()
    expect(screen.getByText('Code')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(screen.getByText('Execute')).toBeInTheDocument()
    expect(screen.getByText('Custom Node')).toBeInTheDocument()
  })

  it('renders descriptions for each node', () => {
    render(<NodePalette isOpen={true} onClose={jest.fn()} />)
    expect(screen.getByText('Classify & route task')).toBeInTheDocument()
    expect(screen.getByText('Add a custom annotation node')).toBeInTheDocument()
  })

  it('calls onClose when close button clicked', () => {
    const onClose = jest.fn()
    render(<NodePalette isOpen={true} onClose={onClose} />)
    fireEvent.click(screen.getByTitle('Close palette'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('sets drag data on drag start', () => {
    render(<NodePalette isOpen={true} onClose={jest.fn()} />)
    const analyzeItem = screen.getByText('Analyze').closest('[draggable]')
    expect(analyzeItem).toBeTruthy()
    expect(analyzeItem?.getAttribute('draggable')).toBe('true')
  })

  it('shows drag hint at bottom', () => {
    render(<NodePalette isOpen={true} onClose={jest.fn()} />)
    expect(screen.getByText(/Drag nodes onto the canvas/i)).toBeInTheDocument()
  })

  it('has a header with the title Nodes', () => {
    render(<NodePalette isOpen={true} onClose={jest.fn()} />)
    expect(screen.getByText('Nodes')).toBeInTheDocument()
  })
})
