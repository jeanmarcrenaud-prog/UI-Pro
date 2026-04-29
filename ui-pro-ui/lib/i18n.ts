// i18n.ts
// Role: Internationalization - externalized strings for UI-Pro
// Supported languages: en (default), fr

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
    copy: 'Copier'
    copied: 'Copié'
    save: 'Enregistrer'
    run: 'Exécuter'
    running: 'Exécution...'
  }
  history: {
    title: string
    empty: string
    confirmDelete: string
  }
}

// Get current locale from localStorage or default to 'en'
function getCurrentLocale(): Locale {
  if (typeof window !== 'undefined') {
    return (localStorage.getItem('locale') as Locale) || 'en'
  }
  return 'en'
}

// Get translations based on current locale
export function useI18n(): Translations {
  return translations[getCurrentLocale()]
}

// Get translations for specific locale
export function getTranslations(locale: Locale): Translations {
  return translations[locale]
}

// Step ID to translation key mapping
export const STEP_STATUS_LABELS: Record<string, keyof Translations['steps']> = {
  'step-analyzing': 'analyzing',
  'step-planning': 'planning',
  'step-executing': 'executing',
  'step-reviewing': 'reviewing',
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
  },
  codeBlock: { copy: 'Copy', copied: 'Copied', save: 'Save' },
  history: { title: 'History', empty: 'No conversations yet', confirmDelete: 'Confirm?' },
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
  },
  codeBlock: { copy: 'Copier', copied: 'Copié', save: 'Enregistrer' },
  history: { title: 'Historique', empty: 'Aucune conversation', confirmDelete: 'Confirmer?' },
}

export const translations = { en, fr }