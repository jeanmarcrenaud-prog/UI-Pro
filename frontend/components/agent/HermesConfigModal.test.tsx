// HermesConfigModal.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { HermesConfigModal, type HermesConfigReport } from './HermesConfigModal'

jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

const readyReport: HermesConfigReport = {
  configured: true,
  base_url: 'http://127.0.0.1:1234/v1',
  model: 'bonsai-2-27b-pq2_0-crack',
  backend: 'lmstudio',
  llm_reachable: true,
  available_models: ['aura-4b'],
  recommended_model: 'aura-4b',
  gpu_headroom_ok: true,
  needs_install: false,
  message: 'Hermes prêt · model: bonsai-2-27b-pq2_0-crack',
}

const warningReport: HermesConfigReport = {
  ...readyReport,
  configured: false,
  base_url: null,
  llm_reachable: false,
  available_models: ['qwen3.8-27b', 'aura-4b'],
  recommended_model: 'aura-4b',
  gpu_headroom_ok: false,
  needs_install: true,
  message: 'Aucun LLM local détecté. Installez LM Studio ou Ollama.',
}

describe('HermesConfigModal', () => {
  const onClose = jest.fn()
  const onApply = jest.fn().mockResolvedValue(undefined)

  beforeEach(() => {
    onClose.mockClear()
    onApply.mockClear()
  })

  it('renders nothing when closed', () => {
    const { container } = render(
      <HermesConfigModal isOpen={false} report={readyReport} onClose={onClose} onApply={onApply} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders message and read-only current config', () => {
    render(
      <HermesConfigModal isOpen report={readyReport} onClose={onClose} onApply={onApply} />,
    )
    expect(screen.getByText(readyReport.message)).toBeInTheDocument()
    expect(screen.getByDisplayValue('http://127.0.0.1:1234/v1')).toBeInTheDocument()
    expect(screen.getByDisplayValue('bonsai-2-27b-pq2_0-crack')).toBeInTheDocument()
  })

  it('renders warning state and applies the recommended model', () => {
    render(
      <HermesConfigModal isOpen report={warningReport} onClose={onClose} onApply={onApply} />,
    )
    expect(screen.getByText(warningReport.message)).toBeInTheDocument()
    fireEvent.click(screen.getByText(/Utiliser aura-4b/))
    expect(onApply).toHaveBeenCalledWith({
      base_url: 'http://127.0.0.1:1234/v1',
      model: 'aura-4b',
    })
  })

  it('calls onClose from Annuler', () => {
    render(
      <HermesConfigModal isOpen report={readyReport} onClose={onClose} onApply={onApply} />,
    )
    fireEvent.click(screen.getByText('Annuler'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
