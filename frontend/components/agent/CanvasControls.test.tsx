// CanvasControls.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { CanvasControls } from './CanvasControls'

describe('CanvasControls', () => {
  it('renders export PNG button', () => {
    render(<CanvasControls onExportPng={jest.fn()} onExportJson={jest.fn()} />)
    expect(screen.getByTitle('Export as PNG')).toBeInTheDocument()
  })

  it('renders export JSON button', () => {
    render(<CanvasControls onExportPng={jest.fn()} onExportJson={jest.fn()} />)
    expect(screen.getByTitle('Export as JSON')).toBeInTheDocument()
  })

  it('calls onExportPng when PNG button clicked', () => {
    const onExportPng = jest.fn()
    render(<CanvasControls onExportPng={onExportPng} onExportJson={jest.fn()} />)
    fireEvent.click(screen.getByTitle('Export as PNG'))
    expect(onExportPng).toHaveBeenCalledTimes(1)
  })

  it('calls onExportJson when JSON button clicked', () => {
    const onExportJson = jest.fn()
    render(<CanvasControls onExportPng={jest.fn()} onExportJson={onExportJson} />)
    fireEvent.click(screen.getByTitle('Export as JSON'))
    expect(onExportJson).toHaveBeenCalledTimes(1)
  })

  it('renders palette toggle button', () => {
    render(<CanvasControls onExportPng={jest.fn()} onExportJson={jest.fn()} onTogglePalette={jest.fn()} />)
    expect(screen.getByTitle('Toggle node palette')).toBeInTheDocument()
  })

  it('calls onTogglePalette when palette button clicked', () => {
    const onTogglePalette = jest.fn()
    render(<CanvasControls onExportPng={jest.fn()} onExportJson={jest.fn()} onTogglePalette={onTogglePalette} />)
    fireEvent.click(screen.getByTitle('Toggle node palette'))
    expect(onTogglePalette).toHaveBeenCalledTimes(1)
  })

  it('shows palette button as active when paletteOpen is true', () => {
    render(
      <CanvasControls
        onExportPng={jest.fn()}
        onExportJson={jest.fn()}
        onTogglePalette={jest.fn()}
        paletteOpen={true}
      />,
    )
    const btn = screen.getByTitle('Toggle node palette')
    expect(btn.className).toContain('violet')
  })

  it('renders split view button when showSplitView is true', () => {
    render(
      <CanvasControls
        onExportPng={jest.fn()}
        onExportJson={jest.fn()}
        onSplitView={jest.fn()}
        showSplitView={true}
      />,
    )
    expect(screen.getByTitle('Toggle split view')).toBeInTheDocument()
  })

  it('hides split view button when showSplitView is false', () => {
    render(
      <CanvasControls
        onExportPng={jest.fn()}
        onExportJson={jest.fn()}
        onSplitView={jest.fn()}
        showSplitView={false}
      />,
    )
    expect(screen.queryByTitle('Toggle split view')).not.toBeInTheDocument()
  })

  it('calls onSplitView when split view button clicked', () => {
    const onSplitView = jest.fn()
    render(
      <CanvasControls
        onExportPng={jest.fn()}
        onExportJson={jest.fn()}
        onSplitView={onSplitView}
        showSplitView={true}
      />,
    )
    fireEvent.click(screen.getByTitle('Toggle split view'))
    expect(onSplitView).toHaveBeenCalledTimes(1)
  })
})
