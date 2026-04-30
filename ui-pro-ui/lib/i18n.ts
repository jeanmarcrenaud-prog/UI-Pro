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
  }
  history: {
    title: string
    empty: string
    confirmDelete: string
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

// ==================== TRANSLATIONS ====================

const translations: Record<Locale, Translations> = {
  en: {
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
    },
    codeBlock: {
      copy: 'Copy',
      copied: 'Copied',
      save: 'Save',
      run: 'Run',
      running: 'Running...',
    },
    history: { title: 'History', empty: 'No conversations yet', confirmDelete: 'Confirm?' },
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
  },

  fr: {
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
    },
    codeBlock: {
      copy: 'Copier',
      copied: 'Copié',
      save: 'Enregistrer',
      run: 'Exécuter',
      running: 'Exécution...',
    },
    history: { title: 'Historique', empty: 'Aucune conversation', confirmDelete: 'Confirmer ?' },
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
  },
}

// ==================== HOOK ====================

export function useI18n() {
  const [locale, setLocale] = useState<Locale>('en')
  const [isClient, setIsClient] = useState(false)

  useEffect(() => {
    setIsClient(true)
    // Only run on client (SSR safe)
    try {
      const savedLocale = localStorage.getItem('locale') as Locale | null
      if (savedLocale && (savedLocale === 'en' || savedLocale === 'fr')) {
        setLocale(savedLocale)
      }
    } catch {
      // localStorage not available
    }
  }, [])

  const changeLocale = (newLocale: Locale) => {
    setLocale(newLocale)
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('locale', newLocale)
      } catch {
        // localStorage not available
      }
    }
  }

  // Return translations directly 
  const currentTranslations = isClient ? translations[locale] : translations.en
  const t = currentTranslations || translations.en

  return {
    t,
    locale,
    setLocale: changeLocale,
  }
}

// ==================== UTILITIES ====================

export function getTranslations(locale: Locale): Translations {
  return translations[locale]
}

export const defaultLocale: Locale = 'en'

// Mapping pour les steps du backend
export const STEP_STATUS_LABELS: Record<string, keyof Translations['steps']> = {
  'step-analyzing': 'analyzing',
  'step-planning': 'planning',
  'step-executing': 'executing',
  'step-reviewing': 'reviewing',
  'step-complete': 'complete',
}