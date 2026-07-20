// MarioView.test.tsx
// Unit tests for the Mario Voice Assistant component

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { MarioView } from './MarioView'

// ── Mock i18n ─────────────────────────────────────────

const mockT = (key: string) => key

jest.mock('@/lib/i18n', () => ({
  useI18n: () => ({
    t: new Proxy({}, { get: () => mockT }),
    locale: 'fr',
    setLocale: jest.fn(),
  }),
}))

// ── Mock framer-motion (skip animations in tests) ─────

jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      // Strip motion-specific props that React doesn't recognize
      const { initial, animate, exit, transition, layout, ...validProps } = props
      return <div {...validProps}>{children}</div>
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

// ── Helpers ────────────────────────────────────────────

const API_BASE = 'http://localhost:8000/api/mario'

function mockFetchSuccess(data: any, status = 200) {
  return jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  })
}

function mockFetchError(status: number, detail: string) {
  return jest.fn().mockResolvedValue({
    ok: false,
    status,
    json: () => Promise.resolve({ detail }),
  })
}

// ── Tests ──────────────────────────────────────────────

describe('MarioView', () => {
  let originalFetch: any

  beforeAll(() => {
    originalFetch = global.fetch
    // scrollIntoView doesn't exist in jsdom
    Element.prototype.scrollIntoView = jest.fn()
  })

  afterEach(() => {
    global.fetch = originalFetch
    jest.clearAllMocks()
  })

  // ── Loading state ──────────────────────────────

  it('shows loading state on mount', () => {
    // Never resolve the fetch
    global.fetch = jest.fn(() => new Promise(() => {}))

    render(<MarioView />)

    expect(screen.getByText(/Connexion à Mario/i)).toBeInTheDocument()
  })

  // ── Available state ────────────────────────────

  it('renders Mario interface when services are available', async () => {
    global.fetch = mockFetchSuccess({
      available: true,
      tts: true,
      stt: false,
      llm: true,
      llm_service: 'ollama',
      voices: ['fr_FR-siwis-medium'],
      models: ['qwen3.5:9b', 'llama3.2:3b'],
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    // The header is a single <p>: "Assistant Vocal Intelligent — Intégré dans UI-Pro"
    expect(screen.getByText(/Assistant Vocal Intelligent — Intégré dans UI-Pro/)).toBeInTheDocument()

    // Check status badges
    expect(screen.getByText('TTS')).toBeInTheDocument()
    expect(screen.getByText('LLM')).toBeInTheDocument()
    // ollama appears in LLM badge label + chat header — use getAllByText
    expect(screen.getAllByText(/ollama/).length).toBeGreaterThanOrEqual(1)

    // Check conversation section
    expect(screen.getByText('Conversation avec Mario')).toBeInTheDocument()

    // Check TTS section
    expect(screen.getByText('Synthèse Vocale (TTS)')).toBeInTheDocument()

    // Check STT section
    expect(screen.getByText('Reconnaissance Vocale (STT)')).toBeInTheDocument()
  })

  it('shows service status badges correctly', async () => {
    global.fetch = mockFetchSuccess({
      available: true,
      tts: true,
      stt: false,
      llm: true,
      llm_service: 'lm_studio',
      voices: ['fr_FR-siwis-medium'],
      models: ['qwen3.5:9b'],
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    // TTS should be shown as active (green)
    const ttsBadge = screen.getByText('TTS')
    expect(ttsBadge).toBeInTheDocument()

    // (lm_studio) appears in LLM badge AND as plain text in chat header
    const lmStudio = screen.getAllByText(/(lm_studio)/)
    expect(lmStudio.length).toBeGreaterThanOrEqual(1)
  })

  it('shows voice and model counts', async () => {
    global.fetch = mockFetchSuccess({
      available: true,
      tts: true,
      stt: false,
      llm: true,
      llm_service: 'ollama',
      voices: ['fr_FR-siwis-medium', 'en_US-lessac-medium'],
      models: ['qwen3.5:9b'],
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    // Check count badges
    expect(screen.getByText(/2 dispo/)).toBeInTheDocument() // voices
    expect(screen.getByText(/1 dispo/)).toBeInTheDocument() // models (or voices depending)
  })

  // ── Unavailable state ──────────────────────────

  it('shows unavailable message when Mario is not available', async () => {
    global.fetch = mockFetchSuccess({
      available: false,
      tts: false,
      stt: false,
      llm: false,
      llm_service: 'none',
      voices: [],
      models: [],
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText(/Mario n'est pas disponible/i)).toBeInTheDocument()
    })

    // Should show a retry button
    expect(screen.getByText('Réessayer')).toBeInTheDocument()
  })

  it('shows error message when fetch fails', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('Network error'))

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText(/Mario n'est pas disponible/i)).toBeInTheDocument()
    })

    // Should show the error detail
    expect(screen.getByText('Network error')).toBeInTheDocument()
  })

  it('retries connection when retry button is clicked', async () => {
    // First call fails
    const fetchMock = jest
      .fn()
      .mockRejectedValueOnce(new Error('Connection failed'))
      // Second call succeeds
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            available: true,
            tts: true,
            stt: false,
            llm: true,
            llm_service: 'ollama',
            voices: ['fr_FR-siwis-medium'],
            models: ['qwen3.5:9b'],
          }),
      })

    global.fetch = fetchMock

    render(<MarioView />)

    // Wait for error state
    await waitFor(() => {
      expect(screen.getByText('Réessayer')).toBeInTheDocument()
    })

    // Click retry
    await act(async () => {
      fireEvent.click(screen.getByText('Réessayer'))
    })

    // Should now show Mario interface
    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })
  })

  // ── Conversation ──────────────────────────────

  it('sends a message and displays the response', async () => {
    let fetchCallCount = 0

    global.fetch = jest.fn().mockImplementation((url: string, options?: any) => {
      fetchCallCount++

      // First call = status fetch
      if (fetchCallCount === 1) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              available: true,
              tts: true,
              stt: false,
              llm: true,
              llm_service: 'ollama',
              voices: ['fr_FR-siwis-medium'],
              models: ['qwen3.5:9b'],
            }),
        })
      }

      // Second call = conversation
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            response: 'Bonjour ! Je suis Mario, votre assistant vocal.',
            service_type: 'ollama',
          }),
      })
    })

    render(<MarioView />)

    // Wait for load
    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    // Type a message
    const input = screen.getByPlaceholderText('Parle à Mario...')
    await act(async () => {
      fireEvent.change(input, { target: { value: 'Bonjour' } })
    })

    // Send it
    const sendButton = screen.getByText('Envoyer')
    await act(async () => {
      fireEvent.click(sendButton)
    })

    // Wait for response
    await waitFor(() => {
      expect(
        screen.getByText('Bonjour ! Je suis Mario, votre assistant vocal.')
      ).toBeInTheDocument()
    })

    // User message should also be visible
    expect(screen.getByText('Bonjour')).toBeInTheDocument()
  })

  it('shows error message when conversation fails', async () => {
    let fetchCallCount = 0

    global.fetch = jest.fn().mockImplementation((url: string, options?: any) => {
      fetchCallCount++

      if (fetchCallCount === 1) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              available: true,
              tts: true,
              stt: false,
              llm: true,
              llm_service: 'ollama',
              voices: ['fr_FR-siwis-medium'],
              models: ['qwen3.5:9b'],
            }),
        })
      }

      return Promise.resolve({
        ok: false,
        status: 503,
        json: () => Promise.resolve({ detail: 'LLM not available' }),
      })
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText('Parle à Mario...')
    await act(async () => {
      fireEvent.change(input, { target: { value: 'Hello' } })
    })

    await act(async () => {
      fireEvent.click(screen.getByText('Envoyer'))
    })

    await waitFor(() => {
      expect(screen.getByText(/LLM not available/)).toBeInTheDocument()
    })
  })

  it('disables send button when input is empty', async () => {
    global.fetch = mockFetchSuccess({
      available: true,
      tts: true,
      stt: false,
      llm: true,
      llm_service: 'ollama',
      voices: [],
      models: [],
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    const sendButton = screen.getByText('Envoyer')
    expect(sendButton).toBeDisabled()
  })

  // ── TTS ───────────────────────────────────────

  it('calls TTS API when speak button is clicked', async () => {
    let fetchCallCount = 0

    global.fetch = jest.fn().mockImplementation((url: string, options?: any) => {
      fetchCallCount++

      if (fetchCallCount === 1) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              available: true,
              tts: true,
              stt: false,
              llm: true,
              llm_service: 'ollama',
              voices: ['fr_FR-siwis-medium'],
              models: ['qwen3.5:9b'],
            }),
        })
      }

      // Conversation or TTS call — check URL
      if (url.includes('/tts/play')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        })
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ response: 'ok', service_type: 'ollama' }),
      })
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    // Type TTS text
    const ttsTextarea = screen.getByPlaceholderText(/Texte à prononcer/)
    await act(async () => {
      fireEvent.change(ttsTextarea, { target: { value: 'Bonjour le monde' } })
    })

    // Click speak button
    await act(async () => {
      // Button text is "🔊 Faire parler Mario" — use regex to ignore emoji prefix
      fireEvent.click(screen.getByText(/Faire parler Mario/))
    })
    await waitFor(() => {
      expect(screen.getByText(/Mario a parlé !/)).toBeInTheDocument()
    })
  })

  it('disables TTS speak button when TTS is unavailable', async () => {
    global.fetch = mockFetchSuccess({
      available: true,
      tts: false, // TTS not available
      stt: false,
      llm: true,
      llm_service: 'ollama',
      voices: [],
      models: ['qwen3.5:9b'],
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    // Button text is "🔊 Faire parler Mario" — use regex to ignore emoji prefix
    const speakButton = screen.getByText(/Faire parler Mario/)
    expect(speakButton).toBeDisabled()
  })

  // ── STT ───────────────────────────────────────

  it('shows file upload area for STT', async () => {
    global.fetch = mockFetchSuccess({
      available: true,
      tts: true,
      stt: false,
      llm: true,
      llm_service: 'ollama',
      voices: [],
      models: [],
    })

    render(<MarioView />)

    await waitFor(() => {
      expect(screen.getByText('Mario')).toBeInTheDocument()
    })

    // Check file upload area
    expect(
      screen.getByText(/Clique pour uploader un fichier audio/)
    ).toBeInTheDocument()
  })
})
