'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useUIStore } from '@/lib/stores/uiStore'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { InputComponent as Input } from '@/components/ui/Input'
import { BadgeComponent as Badge } from '@/components/ui/badge'
import { X, Download, Trash2, Bug, Pause, Play } from 'lucide-react'

export function DebugPanel() {
  const { debugLogs, clearDebugLogs, isDebugEnabled, toggleDebug } = useUIStore()

  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'steps' | 'stream' | 'errors' | 'raw'>('steps')
  const [filter, setFilter] = useState('')
  const [follow, setFollow] = useState(true)

  const scrollRef = useRef<HTMLDivElement>(null)

  // Filtrage
  const filteredLogs = useMemo(() => {
    if (!filter) return debugLogs
    const term = filter.toLowerCase()
    return debugLogs.filter(log =>
      log.step?.toLowerCase().includes(term) ||
      log.content.toLowerCase().includes(term) ||
      log.type.toLowerCase().includes(term)
    )
  }, [debugLogs, filter])

  // Auto-scroll
  useEffect(() => {
    if (follow && scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth'
      })
    }
  }, [filteredLogs, follow])

  const exportLogs = () => {
    const data = JSON.stringify(debugLogs, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `debug-logs-${new Date().toISOString().slice(0,19)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
{/* Debug button - toggle and open panel */}
      <Button
        onClick={() => {
          if (!isDebugEnabled) {
            toggleDebug()
          }
          setIsOpen(!isOpen)
        }}
        variant={isDebugEnabled ? 'primary' : 'secondary'}
        size="sm"
        className="fixed bottom-6 right-6 z-50"
      >
        <Bug className="w-4 h-4 mr-2" />
        {isDebugEnabled ? 'Debug ON' : 'Debug'}
        {isDebugEnabled && debugLogs.length > 0 && (
          <Badge className="ml-2 bg-white text-violet-600 text-xs">
            {debugLogs.length}
          </Badge>
        )}
      </Button>

      <AnimatePresence>
        {isOpen && isDebugEnabled && (
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.96 }}
            className="fixed bottom-20 right-6 w-[520px] h-[640px] bg-[#0f172a] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden z-50 flex flex-col"
          >
            {/* Header */}
            <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between bg-slate-950">
              <div className="flex items-center gap-3">
                <div className="text-violet-400">
                  <Bug className="w-5 h-5" />
                </div>
                <span className="font-semibold text-white">Debug Panel</span>
              </div>

              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setFollow(!follow)}
                  title={follow ? "Pause auto-scroll" : "Activer auto-scroll"}
                >
                  {follow ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>

                <Button variant="ghost" size="sm" onClick={exportLogs} title="Exporter">
                  <Download className="w-4 h-4" />
                </Button>

                <Button variant="ghost" size="sm" onClick={clearDebugLogs} title="Tout effacer">
                  <Trash2 className="w-4 h-4" />
                </Button>

                <Button variant="ghost" size="sm" onClick={() => setIsOpen(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Filtre */}
            <div className="p-3 border-b border-slate-700">
              <Input
                placeholder="Filtrer (step, contenu...)"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-slate-900 border-slate-600 focus:border-violet-500"
              />
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={(v: any) => setActiveTab(v)} className="flex-1 flex flex-col">
              <TabsList className="grid grid-cols-4 bg-transparent border-b border-slate-700 px-4">
                <TabsTrigger value="steps" className="text-xs">Steps</TabsTrigger>
                <TabsTrigger value="stream" className="text-xs">Stream</TabsTrigger>
                <TabsTrigger value="errors" className="text-xs">Errors</TabsTrigger>
                <TabsTrigger value="raw" className="text-xs">Raw</TabsTrigger>
              </TabsList>

              {/* STEPS TAB */}
              <TabsContent value="steps" className="flex-1 m-0 overflow-hidden">
                <div className="h-full overflow-y-auto p-4" ref={scrollRef}>
                  {filteredLogs.filter(l => l.type === 'step').length === 0 ? (
                    <div className="h-full flex items-center justify-center text-slate-500">
                      Aucun step enregistré
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {filteredLogs
                        .filter(l => l.type === 'step')
                        .map((log, i) => (
                          <div key={log.id || i} className="bg-slate-900/80 border border-slate-700 rounded-xl p-4">
                            <div className="flex justify-between items-start">
                              <div className="font-medium text-emerald-400">{log.step}</div>
                              <div className="text-[10px] text-slate-500 font-mono">
                                {new Date(log.timestamp).toLocaleTimeString()}
                              </div>
                            </div>
                            <p className="text-sm text-slate-300 mt-2 leading-relaxed">
                              {log.content}
                            </p>
                            {log.duration && (
                              <div className="text-xs text-slate-500 mt-2">⏱️ {log.duration}ms</div>
                            )}
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* STREAM TAB */}
              <TabsContent value="stream" className="flex-1 m-0 p-4 overflow-auto text-sm font-mono text-slate-400">
                {filteredLogs.filter(l => l.type === 'token' || l.type === 'info').map((log, i) => (
                  <div key={i} className="mb-1">{log.content}</div>
                ))}
              </TabsContent>

              {/* ERRORS TAB */}
              <TabsContent value="errors" className="flex-1 m-0 p-4 overflow-auto">
                {filteredLogs.filter(l => l.type === 'error').length === 0 ? (
                  <p className="text-slate-500 text-center py-12">Aucune erreur</p>
                ) : (
                  filteredLogs
                    .filter(l => l.type === 'error')
                    .map((log, i) => (
                      <div key={i} className="bg-red-950/50 border border-red-900/50 rounded-xl p-4 mb-4">
                        <p className="text-red-400 text-sm">{log.content}</p>
                      </div>
                    ))
                )}
              </TabsContent>

              {/* RAW TAB */}
              <TabsContent value="raw" className="flex-1 m-0 p-4 overflow-auto font-mono text-xs text-slate-500">
                <pre>{JSON.stringify(debugLogs, null, 2)}</pre>
              </TabsContent>
            </Tabs>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}