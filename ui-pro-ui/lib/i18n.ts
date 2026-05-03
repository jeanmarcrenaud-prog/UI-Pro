// lib/i18n.ts
'use client'

import { useState, useEffect } from 'react'

export type Locale = 'en' | 'fr'

export interface Translations {
  welcome: { title: string; subtitle: string }
  input: { placeholder: string }
  steps: {
    analyzing: string
    planning: string
    executing: string
    reviewing: string
    complete: string
    initializing: string
    processing: string
    stepLabel: (current: number, total: number) => string
  }
  streaming: { generating: string }
  loading: { dots: string }
  settings: {
    title: string
    subtitle: string
    modelsSection: string
    defaultModel: string
    modelHelp: string
    availableModels: string
    refresh: string
    refreshing: string
    backendConnections: string
    systemResources: string
    about: string
    language: string
    active: string
    inactive: string
  }
  debug: {
    title: string
    status: string
    model: string
    backend: string
    elapsed: string
    tokens: string
    agentExecution: string
  }
  codeBlock: {
    copy: string
    copied: string
    save: string
    run: string
    running: string
    installing: string
    dependencies: string
  }
  history: {
    title: string
    empty: string
    confirmDelete: string
  }
  suggestions: {
    title: string
    improve: string
    logging: string
    api: string
    tests: string
    types: string
    improvePrompt: string
    loggingPrompt: string
    apiPrompt: string
    testsPrompt: string
    typesPrompt: string
    // MessageSuggestions below responses
    improveCode: string
    addTests: string
    fastapiVersion: string
    makeRobust: string
    convertPackage: string
  }
  sidebar: {
    newChat: string
    recentChats: string
    noChatsYet: string
    discoverModels: string
    noModelsFound: string
    refreshModels: string
    ollama: string
    chat: string
    settings: string
    history: string
  }
}

// ==================== ENGLISH ====================
const en: Translations = {
  welcome: { title: 'Welcome to UI-Pro', subtitle: 'AI Agent System' },
  input: { placeholder: 'Describe your task...' },
  steps: {
    analyzing: 'Analyzing request...',
    planning: 'Planning solution...',
    executing: 'Executing code...',
    reviewing: 'Reviewing results...',
    complete: 'Complete',
    initializing: 'Initializing...',
    processing: 'Processing step...',
    stepLabel: (c, t) => `Step ${c}/${t}`,
  },
  streaming: { generating: 'Generating response...' },
  loading: { dots: 'Loading' },
  settings: {
    title: 'Settings',
    subtitle: 'Configure AI models and backend connections',
    modelsSection: 'Models',
    defaultModel: 'Default Model',
    modelHelp: 'This model will be used for all new chats',
    availableModels: 'Available Models',
    refresh: 'Refresh',
    refreshing: 'Refreshing...',
    backendConnections: 'Backend Connections',
    systemResources: 'System Resources',
    about: 'About',
    language: 'Language',
    active: 'Active',
    inactive: 'Inactive',
  },
  debug: {
    title: 'Debug Panel',
    status: 'Status',
    model: 'Model',
    backend: 'Backend',
    elapsed: 'Elapsed',
    tokens: 'Tokens',
    agentExecution: 'Agent Execution',
    liveLogs: 'Live Logs',
    clear: 'Clear',
    waiting: 'Waiting...',
  },
  codeBlock: { copy: 'Copy', copied: 'Copied', save: 'Save', run: 'Run', running: 'Running...', installing: 'Installing...', dependencies: 'Deps' },
  history: { title: 'History', empty: 'No conversations yet', confirmDelete: 'Confirm?' },
  suggestions: { title: 'Suggestions', improve: 'Improve script', logging: 'Add logging', api: 'Convert to API', tests: 'Add tests', types: 'Add types', improvePrompt: 'Improve this script:\n{code}\n\nImprove with better performance and best practices.', loggingPrompt: 'Add logging and error handling:\n{code}\n\nAdd proper logging and exception handling.', apiPrompt: 'Convert to FastAPI:\n{code}\n\nConvert this to a FastAPI endpoint with proper routing.', testsPrompt: 'Add unit tests:\n{code}\n\nWrite pytest unit tests for this code.', typesPrompt: 'Add TypeScript:\n{code}\n\nAdd proper TypeScript types and interfaces.', improveCode: 'Improve code', addTests: 'Add tests', fastapiVersion: 'FastAPI version', makeRobust: 'Make robust', convertPackage: 'Convert to package' },
  sidebar: {
    newChat: 'New Chat',
    recentChats: 'Recent Chats',
    noChatsYet: 'No chats yet. Start a new one!',
    discoverModels: 'Discovering models...',
    noModelsFound: 'No models found',
    refreshModels: 'Refresh models',
    ollama: 'Ollama',
    chat: 'Chat',
    settings: 'Settings',
    history: 'History',
  },
}

// ==================== FRENCH ====================
const fr: Translations = {
  welcome: { title: 'Bienvenue sur UI-Pro', subtitle: "Système d'Agents IA" },
  input: { placeholder: 'Décrivez votre tâche...' },
  steps: {
    analyzing: 'Analyse en cours...',
    planning: 'Planification en cours...',
    executing: 'Exécution en cours...',
    reviewing: 'Vérification en cours...',
    complete: 'Terminé',
    initializing: 'Initialisation...',
    processing: 'Traitement...',
    stepLabel: (c, t) => `Étape ${c}/${t}`,
  },
  streaming: { generating: 'Génération en cours...' },
  loading: { dots: 'Chargement' },
  settings: {
    title: 'Paramètres',
    subtitle: 'Configurez les modèles IA et les connexions backend',
    modelsSection: 'Modèles',
    defaultModel: 'Modèle par défaut',
    modelHelp: 'Ce modèle sera utilisé pour tous les nouveaux chats',
    availableModels: 'Modèles disponibles',
    refresh: 'Actualiser',
    refreshing: 'Actualisation...',
    backendConnections: 'Connexions Backend',
    systemResources: 'Ressources Système',
    about: 'À propos',
    language: 'Langue',
    active: 'Actif',
    inactive: 'Inactif',
  },
  debug: {
    title: 'Panneau Debug',
    status: 'Statut',
    model: 'Modèle',
    backend: 'Backend',
    elapsed: 'Temps',
    tokens: 'Tokens',
    agentExecution: 'Exécution Agent',
    liveLogs: 'Logs en direct',
    clear: 'Effacer',
    waiting: 'En attente...',
  },
  codeBlock: { copy: 'Copier', copied: 'Copié', save: 'Enregistrer', run: 'Exécuter', running: 'Exécution...', installing: 'Installation...', dependencies: 'Deps' },
  history: { title: 'Historique', empty: 'Aucune conversation', confirmDelete: 'Confirmer ?' },
  suggestions: { title: 'Suggestions', improve: 'Améliorer', logging: 'Ajouter log', api: 'Convertir API', tests: 'Ajouter tests', types: 'Ajouter types', improvePrompt: 'Améliorer ce script:\n{code}\n\nAméliorer avec de meilleures performances et pratiques.', loggingPrompt: 'Ajouter logging et gestion erreurs:\n{code}\n\nAjouter un logging propre et la gestion des exceptions.', apiPrompt: 'Convertir en FastAPI:\n{code}\n\nConvertir en endpoint FastAPI avec routage approprié.', testsPrompt: 'Ajouter tests unitaires:\n{code}\n\nÉcrire des tests pytest pour ce code.', typesPrompt: 'Ajouter TypeScript:\n{code}\n\nAjouter les types et interfaces TypeScript appropriés.', improveCode: 'Améliorer code', addTests: 'Ajouter tests', fastapiVersion: 'Version FastAPI', makeRobust: 'Rendre robuste', convertPackage: 'Convertir package' },
  sidebar: {
    newChat: 'Nouveau Chat',
    recentChats: 'Conversations Récentes',
    noChatsYet: 'Pas encore de conversations. Commencez un nouveau !',
    discoverModels: 'Détection des modèles...',
    noModelsFound: 'Aucun modèle trouvé',
    refreshModels: 'Actualiser les modèles',
    ollama: 'Ollama',
    chat: 'Discussion',
    settings: 'Paramètres',
    history: 'Historique',
  },
}

export const translations = { en, fr }

// ==================== HOOK ====================

export function useI18n() {
  const [locale, setLocaleState] = useState<Locale>('en')
  
  // Load locale from localStorage on mount
  useEffect(() => {
    try {
      const savedLocale = localStorage.getItem('locale') as Locale
      if (savedLocale === 'en' || savedLocale === 'fr') {
        setLocaleState(savedLocale)
      }
    } catch {
      // ignore
    }
  }, [])

  // Get current translations based on locale
  const t = translations[locale]

  const changeLocale = (newLocale: Locale) => {
    setLocaleState(newLocale)
    try {
      localStorage.setItem('locale', newLocale)
    } catch {
      // ignore
    }
  }

  return {
    t,
    locale,
    setLocale: changeLocale,
  }
}

// Alias for getTranslations
export function getTranslations(loc: Locale): Translations {
  return translations[loc]
}

export const defaultLocale: Locale = 'en'

export const STEP_STATUS_LABELS: Record<string, keyof Translations['steps']> = {
  'step-analyzing': 'analyzing',
  'step-planning': 'planning',
  'step-executing': 'executing',
  'step-reviewing': 'reviewing',
  'step-complete': 'complete',
}