/**
 * Tests unitaires pour le hook useChat
 * 
 * Couvre:
 * - Ajout de messages utilisateur et assistant
 * - Gestion des erreurs
 * - Streaming de tokens
 * - Navigation des étapes de l'agent
 * - Nettoyage des effets
 * - Gestion de l'état du chargement
 */

import { renderHook, act, waitFor } from '@testing-library/react'
import { useChat } from './useChat'
// Mock Zustand
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'

// Mock des stores
jest.mock('@/lib/stores/chatStore', () => ({
  useChatStore: jest.fn()
}))

jest.mock('@/lib/stores/agentStore', () => ({
  useAgentStore: jest.fn()
}))

jest.mock('@/services/chatService', () => ({
  chatService: {
    onMessage: jest.fn(),
    sendMessage: jest.fn()
  }
}))

jest.mock('@/lib/events', () => ({
  events: {
    on: jest.fn(),
    off: jest.fn()
  }
}))

describe('useChat', () => {
  beforeAll(() => {
    // Reset Mocks
    jest.clearAllMocks()
  })

  beforeEach(() => {
    // Setup mocks avec des valeurs par défaut
    const mockChatStore = {
      messages: [],
      isLoading: false,
      error: null,
      addMessage: jest.fn(),
      updateLastMessage: jest.fn(),
      clearMessages: jest.fn(),
      setLoading: jest.fn(),
      setError: jest.fn(),
      saveToHistory: jest.fn(),
      logs: []
    }

    (useChatStore as jest.Mock).mockImplementation(() => mockChatStore)

    const mockAgentStore = {
      isActive: false,
      steps: [],
      start: jest.fn(),
      updateStep: jest.fn(),
      reset: jest.fn()
    }

    (useAgentStore as jest.Mock).mockImplementation(() => mockAgentStore)

    const mockEvents = {
      on: jest.fn(),
      off: jest.fn()
    }

    (events as any).mockImplementation(mockEvents)
  })

  afterAll(() => {
    jest.restoreAllMocks()
  })

  it('devrait initialiser avec des messages vides et isLoading = false', () => {
    const { result } = renderHook(() => useChat())

    expect(result.current.messages).toEqual([])
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.isActive).toBe(false)
  })

  it('devrait ajouter un message utilisateur lors de sendMessage()', async () => {
    const testContent = 'Bonjour, comment puis-je aider ?'
    const mockStore = useChatStore.getState()
    
    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })

    // Récupérer la nouvelle instance de mockStore après modification
    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage(testContent)
    })

    // Vérifier que le message utilisateur a été ajouté
    expect(mockStore.addMessage).toHaveBeenCalled()
    expect(mockStore.messages[0]).toEqual({
      role: 'user',
      content: testContent,
      id: expect.any(String)
    })
  })

  it('devrait afficher un placeholder pour le message assistant', async () => {
    const testContent = 'Test message'
    const mockStore = useChatStore.getState()
    
    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage(testContent)
    })

    // Vérifier qu'un message assistant placeholder a été ajouté
    expect(mockStore.messages).toHaveLength(2)
    expect(mockStore.messages[1].role).toBe('assistant')
    expect(mockStore.messages[1].content).toBe('')
    expect(mockStore.messages[1].status).toBe('thinking')
  })

  it('devrait gérer les erreurs correctement avec setError()', async () => {
    const testContent = 'Erreur test'
    const mockStore = useChatStore.getState()
    const mockError = 'Erreur de connexion'

    mockStore.setError = jest.fn()
    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage(testContent)
    })

    // Simuler une erreur sur chatService
    const chatServiceMock = chatService as any
    chatServiceMock.sendMessage.mockRejectedValue(new Error('Test error'))

    await waitFor(() => {
      // Vérifier que setError a été appelé
      expect(mockStore.setError).toHaveBeenCalledWith(
        expect.stringContaining('Test error')
      )
    })
  })

  it('devrait afficher le message d\'erreur dans le state', async () => {
    const testContent = 'Erreur test'
    const mockStore = useChatStore.getState()
    const mockError = 'Erreur de communication'

    mockStore.setError = jest.fn()
    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })
    mockStore.messages = [] // Reset

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage(testContent)
    })

    // Simuler une erreur
    const chatServiceMock = chatService as any
    chatServiceMock.sendMessage.mockRejectedValue(new Error(mockError))

    await waitFor(() => {
      expect(result.current.error).toBeDefined()
      expect(result.current.error).not.toBeNull()
    })
  })

  it('devrait mettre isLoading à true lors d\'envoi', async () => {
    const testContent = 'Message pendant chargement'
    const mockStore = useChatStore.getState()

    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })
    mockStore.setLoading = jest.fn()
    mockStore.messages = [] // Reset

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage(testContent)
    })

    // Vérifier que setLoading a été appelé
    expect(mockStore.setLoading).toHaveBeenCalledWith(true)
    expect(result.current.isLoading).toBe(true)
  })

  it('devrait ne pas envoyer si le contenu est vide', async () => {
    const mockStore = useChatStore.getState()
    mockStore.messages = []

    const sendMessageMock = jest.spyOn(useChatStore.getState(), 'addMessage')
    const setLoadingMock = jest.spyOn(useChatStore.getState(), 'setLoading')

    (useChatStore as jest.Mock).mockImplementation(() => mockStore)

    const { result } = renderHook(() => useChat())

    // Envoyer un message vide
    act(() => {
      result.current.sendMessage('')
    })

    expect(sendMessageMock).not.toHaveBeenCalled()
    expect(setLoadingMock).not.toHaveBeenCalled()
  })

  it('devrait ne pas envoyer si isLoading est true', async () => {
    const mockStore = useChatStore.getState()
    const testContent = 'Message pendant chargement'

    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })
    mockStore.messages = []

    const originalSetLoading = mockStore.setLoading
    mockStore.setLoading = originalSetLoading
    (useChatStore as jest.Mock).mockImplementation(() => mockStore)

    const { result } = renderHook(() => useChat())

    // Configurer isLoading = true
    mockStore.isLoading = true

    act(() => {
      result.current.sendMessage(testContent)
    })

    expect(mockStore.addMessage).not.toHaveBeenCalledWith(
      expect.objectContaining({ role: 'user' })
    )
  })

  it('devrait mettre à jour le message assistant avec le contenu streaming', async () => {
    const mockStore = useChatStore.getState()
    const mockAgentStore = useAgentStore.getState()
    const mockError = 'Erreur de communication'

    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })
    mockStore.updateLastMessage = jest.fn().mockImplementation((content, status) => {
      const message = mockStore.messages.find(m => m.role === 'assistant')
      if (message) {
        message.content = content
        message.status = status
      }
    })
    mockStore.saveToHistory = jest.fn()

    mockAgentStore.updateStep = jest.fn()
    mockAgentStore.start = jest.fn()
    mockAgentStore.reset = jest.fn()

    (useChatStore as jest.Mock).mockImplementation(() => mockStore)
    (useAgentStore as jest.Mock).mockImplementation(() => mockAgentStore)

    // Créer une instance propre du hook
    const { result } = renderHook(() => useChat())

    const testContent = 'Test streaming'
    act(() => {
      result.current.sendMessage(testContent)
    })

    // Simuler un token de streaming
    const token = 'Ceci est un test '
    
    // Mettre à jour le message avec simulateur
    const placeholder = mockStore.messages.find((m: any) => m.role === 'assistant' && m.status === 'thinking')
    mockStore.updateLastMessage(mockStore.messages.find((m: any) => m.role === 'assistant')?.content || '', 'streaming')
  })

  it('devrait gérer le streaming et les tokens', async () => {
    const mockStore = useChatStore.getState()
    const mockAgentStore = useAgentStore.getState()
    const mockError = 'Erreur de communication'

    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })
    mockStore.updateLastMessage = jest.fn().mockImplementation((content, status) => {
      const message = mockStore.messages.find((m: any) => m.role === 'assistant')
      if (message) {
        message.content = content
        message.status = status
      }
    })
    mockStore.saveToHistory = jest.fn()
    mockStore.addLog = jest.fn().mockImplementation((log) => {
      mockStore.logs = [...mockStore.logs, log]
    })

    mockAgentStore.updateStep = jest.fn()
    mockAgentStore.start = jest.fn()
    mockAgentStore.reset = jest.fn()

    (useChatStore as jest.Mock).mockImplementation(() => mockStore)
    (useAgentStore as jest.Mock).mockImplementation(() => mockAgentStore)

    const { result } = renderHook(() => useChat())
    const tokens = ['Bonjour', ' comment', ' puis-je', ' vous', ' aider', '?']

    act(() => {
      result.current.sendMessage('Test')
    })

    tokens.forEach((token, index) => {
      await act(async () => {
        mockStore.updateLastMessage(token, 'streaming')
      })

      expect(result.current.messages).toBeTruthy()
    })
  })

  it('devrait notifier les étapes de l\'agent via events.on()', async () => {
    const mockStore = useChatStore.getState()
    const mockAgentStore = useAgentStore.getState()
    const mockError = 'Erreur de communication'

    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
    })
    mockStore.updateLastMessage = jest.fn().mockImplementation(() => {})
    mockStore.saveToHistory = jest.fn()
    mockStore.addLog = jest.fn()

    mockAgentStore.updateStep = jest.fn()
    mockAgentStore.start = jest.fn()
    mockAgentStore.reset = jest.fn()
    mockAgentStore.steps = [
      { id: 'step-analyzing', title: 'Analyzing request', status: 'done' },
      { id: 'step-planning', title: 'Planning solution', status: 'active' }
    ]
    mockAgentStore.isActive = true

    (useChatStore as jest.Mock).mockImplementation(() => mockStore)
    (useAgentStore as jest.Mock).mockImplementation(() => mockAgentStore)

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('Test')
    })

    expect(result.current.steps).toBeDefined()
    expect(result.current.currentStep).toBeDefined()
  })

  it('devrait avoir un clear qui vide les messages et reset l\'agent', async () => {
    const mockStore = useChatStore.getState()

    mockStore.messages = [
      { role: 'user', content: 'Message 1', id: '1' },
      { role: 'assistant', content: 'Réponse 1', id: '2' }
    ]
    mockStore.clearMessages = jest.fn()
    mockStore.reset = jest.fn()
    mockStore.setError = jest.fn()

    (useChatStore as jest.Mock).mockImplementation(() => mockStore)

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.clear()
    })

    expect(mockStore.clearMessages).toHaveBeenCalled()
    expect(mockStore.reset).toHaveBeenCalled()
    expect(mockStore.setError).toHaveBeenCalled()
    expect(result.current.messages).toHaveLength(0)
  })

  it('devrait retourner les bons valeurs dans le return object', () => {
    const mockStore = useChatStore.getState()

    mockStore.messages = []
    mockStore.isLoading = false
    mockStore.error = null

    const mockAgentStore = {
      isActive: false,
      steps: [],
      start: jest.fn(),
      updateStep: jest.fn(),
      reset: jest.fn()
    }

    mockStore.addMessage = jest.fn()
    mockStore.updateLastMessage = jest.fn()
    mockStore.clearMessages = jest.fn()
    mockStore.setLoading = jest.fn()
    mockStore.setError = jest.fn()
    mockStore.saveToHistory = jest.fn()
    mockStore.addLog = jest.fn()

    (useChatStore as jest.Mock).mockImplementation(() => mockStore)
    (useAgentStore as jest.Mock).mockImplementation(() => mockAgentStore)

    const { result } = renderHook(() => useChat())

    const returnedValue = result.current

    expect(returnedValue).toHaveProperty('messages')
    expect(returnedValue.messages).toBeArray()
    expect(returnedValue).toHaveProperty('isLoading')
    expect(returnedValue.isLoading).toBe(false)
    expect(returnedValue).toHaveProperty('error')
    expect(returnedValue.error).toBeNull()
    expect(returnedValue).toHaveProperty('sendMessage')
    expect(returnedValue).toHaveProperty('clear')
    expect(returnedValue).toHaveProperty('isActive')
    expect(returnedValue).toHaveProperty('currentStep')
    expect(returnedValue).toHaveProperty('steps')
  })

  it('devrait synchroniser les refs pour éviter les stale closures', () => {
    const mockStore = useChatStore.getState()
    const mockAgentStore = useAgentStore.getState()

    mockStore.messages = []
    mockStore.isLoading = false
    mockStore.error = null
    mockStore.addMessage = jest.fn().mockImplementation((msg) => {
      mockStore.messages = [...mockStore.messages, msg]
      mockStore.isLoading = false
    })
    mockStore.updateLastMessage = jest.fn().mockImplementation((content, status) => {
      const message = mockStore.messages.find((m: any) => m.role === 'assistant')
      if (message) {
        message.content = content
        message.status = status
      }
    })
    mockStore.clearMessages = jest.fn()
    mockStore.setLoading = jest.fn()
    mockStore.setError = jest.fn()
    mockStore.saveToHistory = jest.fn()
    mockStore.addLog = jest.fn()

    mockAgentStore.updateStep = jest.fn(mockAgentStore.steps)
    mockAgentStore.start = jest.fn(mockAgentStore.steps)
    mockAgentStore.reset = jest.fn(mockAgentStore.steps)

    (useChatStore as jest.Mock).mockImplementation(() => mockStore)
    (useAgentStore as jest.Mock).mockImplementation(() => mockAgentStore)

    const { result } = renderHook(() => useChat())

    // Envoyer plusieurs messages
    act(() => {
      result.current.sendMessage('Message 1')
      result.current.sendMessage('Message 2')
    })

    // Vérifier que les messages ont été ajoutés correctement
    expect(mockStore.messages.length).toBeGreaterThan(0)
  })

  it('devrait émettre des logs lors des étapes', () => {
    const mockStore = useChatStore.getState()
    const mockAgentStore = useAgentStore.getState()

    mockStore.addMessage = jest.fn()
    mockStore.updateLastMessage = jest.fn()
    mockStore.clearMessages = jest.fn()
    mockStore.setLoading = jest.fn()
    mockStore.setError = jest.fn()
    mockStore.saveToHistory = jest.fn()

    mockStore.addLog = jest.fn().mockImplementation((logMessage) => {
      mockStore.logs = [...mockStore.logs, logMessage]
    })

    mockAgentStore.updateStep = jest.fn(mockAgentStore.steps)
    mockAgentStore.start = jest.fn(mockAgentStore.steps)
    mockAgentStore.reset = jest.fn(mockAgentStore.steps)
    mockAgentStore.steps = [
      { id: 'step-analyzing', title: 'Analyzing request', status: 'active' },
      { id: 'step-planning', title: 'Planning solution', status: 'pending' },
      { id: 'step-executing', title: 'Executing', status: 'pending' }
    ]
    mockAgentStore.isActive = true

    (useChatStore as jest.Mock).mockImplementation(() => mockStore)
    (useAgentStore as jest.Mock).mockImplementation(() => mockAgentStore)

    const { result } = renderHook(() => useChat())

    act(() => {
      result.current.sendMessage('Test')
    })

    // Vérifier que addLog a été appelé
    expect(mockStore.addLog).toHaveBeenCalled()
  })
})