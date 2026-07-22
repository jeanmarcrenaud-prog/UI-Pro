// lib/i18n-types.ts — Pure types, no 'use client'

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
    reloadFromEnv: string
    reloadFromEnvHelp: string
    reloadSuccess: string
    reloadFailed: string
    reloading: string
    seconds: string
    save: string
    saving: string
    logLevel: string
    currentLevel: string
    levelDebug: string
    levelInfo: string
    levelWarning: string
    levelError: string
    levelCritical: string
    levelDescDebug: string
    levelDescInfo: string
    levelDescWarning: string
    levelDescError: string
    levelDescCritical: string
    aboutVersion: string
    thinkingMode: string
    thinkingModeDesc: string
    thinkingModeEnabledHelp: string
    thinkingModeDisabledHelp: string
    thinkingToggleAria: string
    nodeRouting: string
    nodeRoutingDesc: string
    nodeRoutingEnabledHelp: string
    nodeRoutingDisabledHelp: string
    nodeRoutingToggleAria: string
    routingLabelAnalyze: string
    routingLabelPlan: string
    routingLabelCode: string
    routingLabelReview: string
    routingUnset: string
    themeSelector: string
    themeLabelDark: string
    themeLabelLight: string
    themeLabelPurpleRain: string
    themeLabelPro: string
    themeDescDark: string
    themeDescLight: string
    themeDescPurpleRain: string
    themeDescPro: string
    modelCountHeading: string
    modelCountAvailable: string
    metricsLatency: string
    metricsModels: string
    modelFallbackDesc: string
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
    canvas: string
    mario: string
    hermes: string
  }
  canvas: {
    title: string
    pipeline: string
    timeline: string
    exportPng: string
    exportJson: string
    fitView: string
    resetView: string
    filterNodes: string
    splitView: string
    noData: string
    live: string
    status: string
    duration: string
    tokens: string
    detail: string
    approvalPending: string
    approve: string
    reject: string
  }
}
