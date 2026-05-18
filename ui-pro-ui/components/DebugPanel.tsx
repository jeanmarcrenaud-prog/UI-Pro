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
  const { debugLogs, clearDebugLogs, isDebugEnabled } = useUIStore()

  const [isOpen, setIsOpen] = useState(true)
  const [activeTab, setActiveTab] = useState<'steps' | 'stream' | 'errors' | 'raw'>('steps')
  const [filter, setFilter] = useState('')
  const [follow, setFollow] = useState(true)

  const scrollRef = useRef<HTMLDivElement>(null)

  const filteredLogs = useMemo(() => {
    if (!filter) return debugLogs
    const term = filter.toLowerCase()
    return debugLogs.filter(log =>
      log.step?.toLowerCase().includes(term) ||
      log.content.toLowerCase().includes(term) ||
      log.type.includes(term)
    )
  }, [debugLogs, filter])

  // Auto-scroll
  useEffect(() => {
    if (follow && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [filteredLogs, follow])

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
            <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between bg-slate-950/80">
              <div className="flex items-center gap-3">
                <Bug className="w-5 h-5 text-violet-400" />
                <span className="font-semibold text-white tracking-tight">Debug Panel</span>
              </div>

              <div className="flex items-center gap-2">
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
            <div className="p-3 border-b border-slate-700">
              <Input
                placeholder="Filtrer (step, contenu...)"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-slate-900 border-slate-600 placeholder:text-slate-500"
              />
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={(v: any) => setActiveTab(v)} className="flex-1 flex flex-col">
              <TabsList className="grid grid-cols-4 bg-transparent border-b border-slate-700 px-4 py-2">
                <TabsTrigger value="steps" className="text-xs">Steps</TabsTrigger>
                <TabsTrigger value="stream" className="text-xs">Stream</TabsTrigger>
                <TabsTrigger value="errors" className="text-xs">Errors</TabsTrigger>
                <TabsTrigger value="raw" className="text-xs">Raw</TabsTrigger>
              </TabsList>

              {/* STEPS TAB */}
              <TabsContent value="steps" className="flex-1 m-0 overflow-hidden">
                <div className="h-full overflow-y-auto p-4" ref={scrollRef}>
                  {debugLogs.filter(l => l.type === 'step').length === 0 ? (
                    <div className="h-full flex items-center justify-center text-slate-500">
                      Aucun step enregistré
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {debugLogs
                        .filter(l => l.type === 'step')
                        .map((log, idx) => (
                          <div key={idx} className="bg-slate-900/70 border border-slate-700 rounded-xl p-4">
                            <div className="flex items-center justify-between">
                              <div className="font-medium text-violet-300">{log.step}</div>
                              <Badge variant="secondary">
                                {log.step}
                              </Badge>
                            </div>
                            <p className="text-sm text-slate-400 mt-2">{log.content}</p>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* STREAM TAB */}
              <TabsContent value="stream" className="flex-1 m-0 p-4 font-mono text-sm overflow-auto text-slate-400">
                {filteredLogs.filter(l => l.type === 'token').map((log, i) => (
                  <div key={i}>{log.content}</div>
                ))}
              </TabsContent>

              {/* ERRORS TAB */}
              <TabsContent value="errors" className="flex-1 m-0 p-4 overflow-auto">
                {filteredLogs.filter(l => l.type === 'error').length === 0 ? (
                  <p className="text-center text-slate-500 py-12">Aucune erreur détectée</p>
                ) : (
                  filteredLogs.filter(l => l.type === 'error').map((log, i) => (
                    <div key={i} className="bg-red-950 border border-red-800 rounded-xl p-4 mb-3">
                      <p className="text-red-400">{log.content}</p>
                    </div>
                  ))
                )}
              </TabsContent>

              {/* RAW TAB */}
              <TabsContent value="raw" className="flex-1 m-0 p-4 overflow-auto text-xs font-mono text-slate-500">
                <pre>{JSON.stringify(debugLogs, null, 2)}</pre>
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