'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { useAgentStore } from '@/lib/stores/agentStore'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { InputComponent as Input } from '@/components/ui/input'
import { BadgeComponent as Badge } from '@/components/ui/badge'
import { X, Download, Trash2, Bug, Pause, Play, Code, ChevronDown, ChevronRight } from 'lucide-react'

/** Canonical pipeline step IDs — matches StepProgress.tsx */
const PIPELINE_STEP_IDS = new Set([
  'step-analyzing',
  'step-planning',
  'step-coding',
  'step-reviewing',
  'step-executing',
])

export function DebugPanel() {
  const { debugLogs, clearDebugLogs } = useUIStore()
  const currentCode = useChatStore((s) => s.currentCode)
  const messages = useChatStore((s) => s.messages)
  const tokenCount = useChatStore((s) => s.tokenCount)
  const { steps: agentSteps } = useAgentStore()

  const [isOpen, setIsOpen] = useState(true)
  const [activeTab, setActiveTab] = useState<'steps' | 'response' | 'stream' | 'errors' | 'raw'>('response')
  const [filter, setFilter] = useState('')
  const [follow, setFollow] = useState(true)
  const [showExtraEvents, setShowExtraEvents] = useState(false)

  const scrollStepsRef = useRef<HTMLDivElement>(null)
  const scrollResponseRef = useRef<HTMLDivElement>(null)
  const scrollStreamRef = useRef<HTMLDivElement>(null)

  // Split agent steps into canonical pipeline vs extra raw events
  const { pipelineSteps, extraSteps } = useMemo(() => {
    const pipeline: typeof agentSteps = []
    const extra: typeof agentSteps = []
    for (const s of agentSteps) {
      if (PIPELINE_STEP_IDS.has(s.id)) pipeline.push(s)
      else extra.push(s)
    }
    return { pipelineSteps: pipeline, extraSteps: extra }
  }, [agentSteps])

  const filteredLogs = useMemo(() => {
    if (!filter) return debugLogs
    const term = filter.toLowerCase()
    return debugLogs.filter(log =>
      log.step?.toLowerCase().includes(term) ||
      log.content.toLowerCase().includes(term) ||
      log.type.includes(term)
    )
  }, [debugLogs, filter])

  // Auto-scroll active tab
  useEffect(() => {
    if (!follow) return
    const target = activeTab === 'steps' ? scrollStepsRef :
                   activeTab === 'response' ? scrollResponseRef :
                   activeTab === 'stream' ? scrollStreamRef : null
    if (target?.current) {
      target.current.scrollTop = target.current.scrollHeight
    }
  }, [filteredLogs, currentCode, agentSteps, follow, activeTab])

  const exportLogs = () => {
    const data = JSON.stringify(debugLogs, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ui-pro-debug-${new Date().toISOString().slice(0,19)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="fixed bottom-20 right-6 w-[520px] h-[640px] bg-[#0f172a] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden z-50 flex flex-col"
          >
            {/* Header */}
            <div className="px-5 py-4 border-b border-slate-700 flex items-center justify-between bg-slate-950/80">
              <div className="flex items-center gap-3">
                <Bug className="w-5 h-5 text-violet-400" />
                <span className="font-semibold text-white tracking-tight">Debug Panel</span>
              </div>

              <div className="flex items-center gap-2.5">
                <Button variant="ghost" size="sm" onClick={() => setFollow(!follow)}>
                  {follow ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>

                <Button variant="ghost" size="sm" onClick={exportLogs}>
                  <Download className="w-4 h-4" />
                </Button>

                <Button variant="ghost" size="sm" onClick={clearDebugLogs}>
                  <Trash2 className="w-4 h-4" />
                </Button>

                <Button variant="ghost" size="sm" onClick={() => setIsOpen(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Filter */}
            <div className="p-4 border-b border-slate-700">
              <Input
                placeholder="Filtrer (step, contenu...)"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-slate-900 border-slate-600 placeholder:text-slate-500"
              />
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={(v: any) => setActiveTab(v)} className="flex-1 flex flex-col">
              <TabsList className="grid grid-cols-5 bg-transparent border-b border-slate-700 px-4 py-2">
                <TabsTrigger value="steps" className="text-xs">Steps</TabsTrigger>
                <TabsTrigger value="response" className="text-xs">Response</TabsTrigger>
                <TabsTrigger value="stream" className="text-xs">Stream</TabsTrigger>
                <TabsTrigger value="errors" className="text-xs">Errors</TabsTrigger>
                <TabsTrigger value="raw" className="text-xs">Raw</TabsTrigger>
              </TabsList>

              {/* STEPS TAB */}
              <TabsContent value="steps" className="flex-1 m-0 min-h-0 overflow-hidden">
                <div className="h-full overflow-y-auto p-5 space-y-3" ref={scrollStepsRef}>
                  {/* Pipeline steps (canonical 5) */}
                  {pipelineSteps.length > 0 && (
                    <div>
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Pipeline</div>
                      <div className="space-y-1.5">
                        {pipelineSteps.map((step) => (
                          <div key={step.id} className="flex items-center gap-3 bg-slate-900/50 border border-slate-700/60 rounded-lg px-3 py-2">
                            <span className={`w-2 h-2 rounded-full shrink-0 ${
                              step.status === 'active' ? 'bg-emerald-400 animate-pulse' :
                              step.status === 'done' ? 'bg-emerald-500' :
                              step.status === 'error' ? 'bg-red-500' :
                              'bg-slate-600'
                            }`} />
                            <span className={`text-xs font-medium ${
                              step.status === 'active' ? 'text-emerald-300' :
                              step.status === 'done' ? 'text-slate-300' :
                              step.status === 'error' ? 'text-red-400' :
                              'text-slate-500'
                            }`}>{step.title}</span>
                            {step.detail && (
                              <span className="text-[11px] text-slate-500 ml-auto truncate max-w-[250px] text-right">{step.detail}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Extra raw events (collapsible) */}
                  {extraSteps.length > 0 && (
                    <div className="border-t border-slate-700/50 pt-3">
                      <button
                        onClick={() => setShowExtraEvents(!showExtraEvents)}
                        className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider hover:text-slate-300 transition-colors w-full text-left"
                      >
                        {showExtraEvents ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                        Raw Events
                        <span className="text-[10px] font-normal normal-case text-slate-600 ml-1">({extraSteps.length})</span>
                      </button>
                      <AnimatePresence>
                        {showExtraEvents && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="space-y-1 mt-2 overflow-hidden"
                          >
                            {extraSteps.map((step) => (
                              <div key={step.id} className="flex items-center gap-2 bg-slate-900/30 border border-slate-700/40 rounded-md px-2.5 py-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-slate-600 shrink-0" />
                                <span className="text-[11px] text-slate-500 font-mono">{step.id.replace('step-', '')}</span>
                                {step.detail && (
                                  <span className="text-[10px] text-slate-600 ml-auto truncate max-w-[200px] text-right">{step.detail}</span>
                                )}
                              </div>
                            ))}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  {/* Empty state */}
                  {pipelineSteps.length === 0 && debugLogs.filter(l => l.type === 'step').length === 0 && (
                    <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                      Aucun step enregistré
                    </div>
                  )}

                  {/* Event Log */}
                  {debugLogs.filter(l => l.type === 'step').length > 0 && (
                    <div className="border-t border-slate-700/50 pt-3">
                      <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">Event Log</div>
                      <div className="space-y-2">
                        {debugLogs
                          .filter(l => l.type === 'step')
                          .map((log, idx) => (
                            <div key={idx} className="bg-slate-900/70 border border-slate-700 rounded-xl p-3">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-xs font-medium text-violet-300">{log.step}</span>
                                {log.duration && (
                                  <Badge variant="secondary" className="text-[10px]">{log.duration}ms</Badge>
                                )}
                              </div>
                              <p className="text-xs text-slate-400 font-mono leading-relaxed">{log.content}</p>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* RESPONSE TAB */}
              <TabsContent value="response" className="flex-1 m-0 min-h-0 overflow-hidden">
                <div className="h-full flex flex-col">
                  <div className="px-5 py-3 border-b border-slate-700 flex items-center gap-3 text-xs text-[var(--text-muted)]">
                    <Code className="w-3.5 h-3.5" />
                    <span>Contenu en cours de génération</span>
                    {tokenCount > 0 && (
                      <Badge variant="secondary" className="text-[10px] ml-auto">{tokenCount} tokens</Badge>
                    )}
                  </div>
                  <div className="flex-1 overflow-y-auto p-5" ref={scrollResponseRef}>
                    {currentCode ? (
                      <pre className="text-xs text-slate-300 font-mono leading-relaxed whitespace-pre-wrap break-words">
                        {currentCode}
                      </pre>
                    ) : messages.length > 0 ? (
                      <pre className="text-xs text-slate-400 font-mono leading-relaxed whitespace-pre-wrap break-words">
                        {messages.filter(m => m.role === 'assistant').map(m => m.content).join('\n\n---\n\n')}
                      </pre>
                    ) : (
                      <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                        En attente de réponse...
                      </div>
                    )}
                  </div>
                </div>
              </TabsContent>

              {/* STREAM TAB */}
              <TabsContent value="stream" className="flex-1 m-0 min-h-0 overflow-hidden">
                <div className="h-full overflow-y-auto p-5 font-mono text-sm text-[var(--text-muted)]" ref={scrollStreamRef}>
                  <div className="space-y-0.5">
                  {filteredLogs.filter(l => l.type === 'token').map((log, i) => (
                    <span key={i}>{log.content}</span>
                  ))}
                </div>
                </div>
              </TabsContent>

              {/* ERRORS TAB */}
              <TabsContent value="errors" className="flex-1 m-0 min-h-0 overflow-hidden">
                <div className="h-full overflow-auto p-4">
                  {filteredLogs.filter(l => l.type === 'error').length === 0 ? (
                    <p className="text-center text-slate-500 py-12">Aucune erreur détectée</p>
                  ) : (
                    filteredLogs.filter(l => l.type === 'error').map((log, i) => (
                      <div key={i} className="bg-red-950 border border-red-800 rounded-xl p-4 mb-3">
                        <p className="text-red-400">{log.content}</p>
                      </div>
                    ))
                  )}
                </div>
              </TabsContent>

              {/* RAW TAB */}
              <TabsContent value="raw" className="flex-1 m-0 min-h-0 overflow-hidden">
                <div className="h-full overflow-auto p-4 text-xs font-mono text-slate-500">
                  <pre>{JSON.stringify(debugLogs, null, 2)}</pre>
                </div>
              </TabsContent>
            </Tabs>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Debug button */}
      <Button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-50 bg-violet-600 hover:bg-violet-700 text-white shadow-lg"
        size="sm"
      >
        <Bug className="w-4 h-4 mr-2" />
        Debug {isOpen ? 'ON' : 'OFF'}
      </Button>
    </>
  )
}