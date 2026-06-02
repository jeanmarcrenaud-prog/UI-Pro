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
    coding: string
    executing: string
    reviewing: string
    fixing: string
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
    searchModels: string
    testBackends: string
    testBackendsAria: string
    loadingDescription: string
    error: string
    backendConnections: string
    systemResources: string
    about: string
    language: string
    active: string
    inactive: string
    timeouts: string
    llmTimeout: string
    executorTimeout: string
    llmTimeoutHelp: string
    executorTimeoutHelp: string
    savedSuccess: string
    saveFailed: string
    seconds: string
  }
  debug: {
    title: string
    status: string
    model: string
    backend: string
    elapsed: string
    tokens: string
    agentExecution: string
    liveLogs: string
    clear: string
    waiting: string
    generatedCode: string
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
  messageBubble: {
    regenerate: string
    continue: string
    copy: string
    copied: string
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
    coding: 'Generating code...',
    executing: 'Executing code...',
    reviewing: 'Reviewing results...',
    fixing: 'Auto-fixing...',
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
    searchModels: 'Search models...',
    testBackends: 'Test',
    testBackendsAria: 'Test backend connectivity',
    loadingDescription: 'Loading description...',
    error: 'Error',
    backendConnections: 'Backend Connections',
    systemResources: 'System Resources',
    about: 'About',
    language: 'Language',
    active: 'Active',
    inactive: 'Inactive',
    timeouts: 'Timeouts',
    llmTimeout: 'LLM Timeout',
    executorTimeout: 'Execution Timeout',
    llmTimeoutHelp: 'Max time for model responses (10–1800s)',
    executorTimeoutHelp: 'Max time for code execution (5–600s)',
    savedSuccess: 'Saved successfully',
    saveFailed: 'Failed to save',
    seconds: 's',
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
    generatedCode: 'Generated Code',
  },
  codeBlock: { copy: 'Copy', copied: 'Copied', save: 'Save', run: 'Run', running: 'Running...', installing: 'Installing...', dependencies: 'Deps' },
  messageBubble: { regenerate: 'Regenerate', continue: 'Continue', copy: 'Copy', copied: 'Copied' },
  history: { title: 'History', empty: 'No conversations yet', confirmDelete: 'Confirm?' },
  suggestions: { title: 'Suggestions', improve: 'Improve script', logging: 'Add logging', api: 'Convert to API', tests: 'Add tests', types: 'Add types', improvePrompt: `Review and improve this code. Focus on:
- Performance (algorithmic complexity, unnecessary work, blocking I/O)
- Readability (naming, structure, comments where non-obvious)
- Correctness (edge cases, error handling, type safety)
- Pythonic style (idiomatic patterns, stdlib where appropriate)

Constraints:
- Preserve the public API (function signatures, return types)
- Do not introduce new external dependencies
- Keep the diff focused — fix what's broken, don't refactor what's fine

Output:
1. Brief diagnosis (one line per issue)
2. Improved code with inline comments explaining non-obvious changes
3. One-paragraph summary of what changed and why

{code}`, loggingPrompt: `Add structured logging and proper error handling to this code.

For logging (use the \`logging\` module, never print):
- DEBUG: verbose flow (function entry, intermediate values)
- INFO: state changes, lifecycle events
- WARNING: recoverable issues, deprecated usage
- ERROR: failures that affect the user
- Use lazy formatting: logger.debug("got %s", x) not logger.debug(f"got {x}")
- Include context: logger name (auto), exception info via exc_info=True

For error handling:
- Catch specific exceptions (e.g., ValueError, KeyError) — never bare \`except:\`
- Re-raise with \`raise NewError(...) from e\` to preserve the chain
- Fail loud — log + re-raise, don't silently swallow

{code}`, apiPrompt: `Convert this into a FastAPI endpoint.

- Pydantic v2 models for request and response (with type validation, not just dicts)
- Use proper status codes: 200/201/204 for success, 400/404/422 for client errors
- Add a docstring — it becomes the OpenAPI summary
- Use async def if the underlying work is I/O-bound (DB, HTTP, file I/O)
- Add input validation in the route, not in the model alone
- Include CORS middleware if a frontend will call this

Output the full file as a complete, runnable module (imports + app + endpoint + if __name__ == "__main__" guard with uvicorn.run).

{code}`, testsPrompt: `Write pytest tests for this code.

Structure:
- One test function per behavior, not per function
- Use @pytest.mark.parametrize for table-driven cases (input → expected)
- Use fixtures for shared setup (avoid duplication across tests)
- Group related tests in a class if they share setup

Coverage targets:
- Happy path (typical inputs)
- Edge cases (empty, None, boundary values, single element, max size)
- Error cases (invalid input, exceptions, side effects)
- Performance: one test asserting the function is fast enough on a realistic input

Style:
- Clear names: test_<function>_<scenario>_<expected>
- Assert specific values, not just truthiness
- Use tmp_path for filesystem, monkeypatch for env vars, mocker.patch for external calls
- Aim for 80%+ line coverage of the code under test

{code}`, typesPrompt: `Add TypeScript types to this JavaScript code.

For each function:
- Declare parameter types (avoid \`any\`; use \`unknown\` if truly dynamic)
- Declare the return type
- Use generics where applicable: <T>, <K extends keyof T>, etc.

For objects:
- Use \`interface\` for public API shapes (extensible)
- Use \`type\` for unions, intersections, mapped/conditional types
- Mark immutable properties with \`readonly\`
- Use \`as const\` for literal arrays/tuples

Configuration:
- Enable strict mode in tsconfig.json if not already
- Add JSDoc for non-obvious behavior (especially side effects)

Output the typed file plus any new interfaces/types at the top.

{code}`, improveCode: 'Improve code', addTests: 'Add tests', fastapiVersion: 'FastAPI version', makeRobust: 'Make robust', convertPackage: 'Convert to package' },
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
    coding: 'Génération du code...',
    executing: 'Exécution en cours...',
    reviewing: 'Vérification en cours...',
    fixing: 'Correction auto...',
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
    searchModels: 'Rechercher des modèles...',
    testBackends: 'Tester',
    testBackendsAria: 'Tester la connectivité backend',
    loadingDescription: 'Chargement de la description...',
    error: 'Erreur',
    backendConnections: 'Connexions Backend',
    systemResources: 'Ressources Système',
    about: 'À propos',
    language: 'Langue',
    active: 'Actif',
    inactive: 'Inactif',
    timeouts: 'Timeouts',
    llmTimeout: 'Timeout LLM',
    executorTimeout: "Timeout d'exécution",
    llmTimeoutHelp: "Temps max pour les réponses du modèle (10–1800s)",
    executorTimeoutHelp: 'Temps max pour exécuter le code (5–600s)',
    savedSuccess: 'Enregistré avec succès',
    saveFailed: "Échec de l'enregistrement",
    seconds: 's',
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
    generatedCode: 'Code Généré',
  },
  codeBlock: { copy: 'Copier', copied: 'Copié', save: 'Enregistrer', run: 'Exécuter', running: 'Exécution...', installing: 'Installation...', dependencies: 'Deps' },
  messageBubble: { regenerate: 'Régénérer', continue: 'Continuer', copy: 'Copier', copied: 'Copié' },
  history: { title: 'Historique', empty: 'Aucune conversation', confirmDelete: 'Confirmer ?' },
  suggestions: { title: 'Suggestions', improve: 'Améliorer', logging: 'Ajouter log', api: 'Convertir API', tests: 'Ajouter tests', types: 'Ajouter types', improvePrompt: `Revois et améliore ce code. Concentre-toi sur :
- Performance (complexité algorithmique, travail inutile, I/O bloquante)
- Lisibilité (nommage, structure, commentaires là où c'est non évident)
- Correction (cas limites, gestion d'erreurs, sûreté du typage)
- Style pythonique (idiomes, stdlib quand c'est approprié)

Contraintes :
- Préserve l'API publique (signatures, types de retour)
- N'introduis pas de nouvelles dépendances externes
- Reste focalisé — corrige ce qui est cassé, ne refactore pas ce qui marche

Sortie :
1. Diagnostic bref (une ligne par problème)
2. Code amélioré avec commentaires expliquant les changements non évidents
3. Résumé en un paragraphe de ce qui a changé et pourquoi

{code}`, loggingPrompt: `Ajoute du logging structuré et une gestion d'erreurs propre à ce code.

Pour le logging (utilise le module \`logging\`, jamais print) :
- DEBUG : flux verbeux (entrée de fonction, valeurs intermédiaires)
- INFO : changements d'état, événements de cycle de vie
- WARNING : problèmes récupérables, usage déprécié
- ERROR : échecs qui affectent l'utilisateur
- Formatage paresseux : logger.debug("reçu %s", x) et non logger.debug(f"reçu {x}")
- Inclus le contexte : nom du logger (auto), info d'exception via exc_info=True

Pour la gestion d'erreurs :
- Capture des exceptions spécifiques (ex. ValueError, KeyError) — jamais \`except:\` nu
- Relance avec \`raise NewError(...) from e\` pour préserver la chaîne
- Échec bruyant — log + relance, n'avale jamais en silence

{code}`, apiPrompt: `Convertis ceci en endpoint FastAPI.

- Modèles Pydantic v2 pour requête et réponse (avec validation de types, pas juste des dicts)
- Codes HTTP appropriés : 200/201/204 pour succès, 400/404/422 pour erreurs client
- Ajoute une docstring — elle devient le résumé OpenAPI
- Utilise async def si le travail sous-jacent est I/O-bound (BDD, HTTP, fichier)
- Valide les entrées dans la route, pas uniquement dans le modèle
- Inclus le middleware CORS si un frontend va appeler cet endpoint

Sors le fichier complet comme module exécutable (imports + app + endpoint + garde if __name__ == "__main__" avec uvicorn.run).

{code}`, testsPrompt: `Écris des tests pytest pour ce code.

Structure :
- Une fonction de test par comportement, pas par fonction
- Utilise @pytest.mark.parametrize pour les cas en table (entrée → attendu)
- Utilise des fixtures pour le setup partagé (évite la duplication)
- Groupe les tests liés dans une classe s'ils partagent le setup

Couverture visée :
- Chemin nominal (entrées typiques)
- Cas limites (vide, None, valeurs limites, un seul élément, taille max)
- Cas d'erreur (entrée invalide, exceptions, effets de bord)
- Performance : un test qui vérifie que la fonction est assez rapide sur une entrée réaliste

Style :
- Noms clairs : test_<fonction>_<scénario>_<attendu>
- Assertions sur valeurs spécifiques, pas juste truthiness
- Utilise tmp_path pour le filesystem, monkeypatch pour les env vars, mocker.patch pour les appels externes
- Vise 80%+ de couverture de ligne du code testé

{code}`, typesPrompt: `Ajoute des types TypeScript à ce code JavaScript.

Pour chaque fonction :
- Déclare les types de paramètres (évite \`any\` ; utilise \`unknown\` si vraiment dynamique)
- Déclare le type de retour
- Utilise des génériques là où c'est applicable : <T>, <K extends keyof T>, etc.

Pour les objets :
- Utilise \`interface\` pour les formes d'API publique (extensibles)
- Utilise \`type\` pour unions, intersections, types mappés/conditionnels
- Marque les propriétés immuables avec \`readonly\`
- Utilise \`as const\` pour les tableaux/tuples littéraux

Configuration :
- Active strict mode dans tsconfig.json si pas déjà fait
- Ajoute du JSDoc pour les comportements non évidents (surtout les effets de bord)

Sors le fichier typé plus les nouvelles interfaces/types en haut.

{code}`, improveCode: 'Améliorer code', addTests: 'Ajouter tests', fastapiVersion: 'Version FastAPI', makeRobust: 'Rendre robuste', convertPackage: 'Convertir package' },
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
  'step-coding': 'coding',
  'step-executing': 'executing',
  'step-reviewing': 'reviewing',
  'step-fixing': 'fixing',
  'step-complete': 'complete',
}