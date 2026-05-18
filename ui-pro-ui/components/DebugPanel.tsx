// DebugPanel.tsx
// Role: Debug sidebar panel - displays agent execution status, model info, step progress, live logs

'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useUIStore } from '@/lib/stores/uiStore'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { X, Play, Pause, Download, Trash2, Bug } from 'lucide-react'

export function DebugPanel() {
  const { debugLogs, clearDebugLogs, isDebugEnabled } = useUIStore()

  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<'steps' | 'stream' | 'errors' | 'raw'>('steps')
  const [follow, setFollow] = useState(true)
  const [filter, setFilter] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)

  const scrollRef = useRef<HTMLDivElement>(null)

  // Smart filtering
  const filteredLogs = useMemo(() => {
    return debugLogs
      .filter(log => {
        if (!filter) return true
        const search = filter.toLowerCase()
        return (
          log.step?.toLowerCase().includes(search) ||
          log.content.toLowerCase().includes(search) ||
          log.type.includes(search)
        )
      })
      .sort((a, b) => a.timestamp - b.timestamp)
  }, [debugLogs, filter])

  // Auto-scroll
  useEffect(() => {
    if (follow && autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [filteredLogs, follow, autoScroll])

  const exportLogs = () => {
    const dataStr = JSON.stringify(debugLogs, null, 2)
    const dataUri = `data:application/json;charset=utf-8,${encodeURIComponent(dataStr)}`
    const exportFileDefaultName = `ui-pro-debug-${new Date().toISOString().slice(0, 19)}.json`

    const linkElement = document.createElement('a')
    linkElement.setAttribute('href', dataUri)
    linkElement.setAttribute('download', exportFileDefaultName)
    linkElement.click()
  }

  const clearAll = () => {
    if (confirm('Effacer tous les logs de debug ?')) {
      clearDebugLogs()
    }
  }

  if (!isDebugEnabled) return null

  return (
    <>
      {/* Floating button */}
      <Button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-50 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-white shadow-xl"
        size="sm"
      >
        <Bug className="w-4 h-4 mr-2" />
        Debug
        {debugLogs.length > 0 && (
          <Badge variant="secondary" className="ml-2 bg-violet-500 text-white">
            {debugLogs.length}
          </Badge>
        )}
      </Button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-20 right-6 w-[520px] h-[620px] bg-[#0f172a] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden z-50 flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-950">
              <div className="flex items-center gap-2">
                <Bug className="w-5 h-5 text-violet-400" />
                <h3 className="font-semibold text-white">Debug Panel</h3>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setFollow(!follow)}
                  className="text-xs"
                >
                  {follow ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>

                <Button variant="ghost" size="sm" onClick={exportLogs}>
                  <Download className="w-4 h-4" />
                </Button>

                <Button variant="ghost" size="sm" onClick={clearAll}>
                  <Trash2 className="w-4 h-4" />
                </Button>

                <Button variant="ghost" size="sm" onClick={() => setIsOpen(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Search */}
            <div className="px-4 py-2 border-b border-slate-700">
              <input
                type="text"
                placeholder="Filtrer (step, content...)"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-violet-500"
              />
            </div>

            {/* Tabs */}
            <Tabs
              value={activeTab}
              onValueChange={(v) => setActiveTab(v as typeof activeTab)}
              className="flex-1 flex flex-col"
            >
              <TabsList className="grid grid-cols-4 bg-transparent border-b border-slate-700 px-4 pt-2">
                <TabsTrigger value="steps" className="text-xs">Steps</TabsTrigger>
                <TabsTrigger value="stream" className="text-xs">Stream</TabsTrigger>
                <TabsTrigger value="errors" className="text-xs">Errors</TabsTrigger>
                <TabsTrigger value="raw" className="text-xs">Raw</TabsTrigger>
              </TabsList>

              <TabsContent value="steps" className="flex-1 m-0 overflow-hidden">
                <ScrollArea className="h-full" ref={scrollRef}>
                  <div className="p-4 space-y-3">
                    {filteredLogs.filter((l) => l.type === 'step').length === 0 ? (
                      <p className="text-slate-500 text-center py-8">Aucun step enregistré</p>
                    ) : (
                      filteredLogs
                        .filter((l) => l.type === 'step')
                        .map((log) => (
                          <div
                            key={log.id}
                            className="bg-slate-900/70 border border-slate-700 rounded-lg p-3"
                          >
                            <div className="flex justify-between text-xs">
                              <span className="text-emerald-400 font-mono">{log.step}</span>
                              <span className="text-slate-500">
                                {new Date(log.timestamp).toLocaleTimeString()}
                              </span>
                            </div>
                            <p className="text-sm text-slate-300 mt-1">{log.content}</p>
                            {log.duration && (
                              <p className="text-[10px] text-slate-500 mt-1">
                                ⏱️ {log.duration}ms
                              </p>
                            )}
                          </div>
                        ))
                    )}
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="stream" className="flex-1 m-0 overflow-hidden">
                <ScrollArea className="h-full">
                  <div className="p-4 space-y-2">
                    {filteredLogs.filter((l) => l.type === 'token').length === 0 ? (
                      <p className="text-slate-500 text-center py-8">Aucun token enregistré</p>
                    ) : (
                      filteredLogs
                        .filter((l) => l.type === 'token')
                        .map((log) => (
                          <div
                            key={log.id}
                            className="text-xs font-mono text-slate-400 border-b border-slate-800 pb-1"
                          >
                            <span className="text-violet-400">{log.tokens || 0}</span> tokens -{' '}
                            {log.content.slice(0, 100)}
                            {log.content.length > 100 && '...'}
                          </div>
                        ))
                    )}
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="errors" className="flex-1 m-0 overflow-hidden">
                <ScrollArea className="h-full">
                  <div className="p-4 space-y-2">
                    {filteredLogs.filter((l) => l.type === 'error').length === 0 ? (
                      <p className="text-slate-500 text-center py-8">Aucune erreur</p>
                    ) : (
                      filteredLogs
                        .filter((l) => l.type === 'error')
                        .map((log) => (
                          <div
                            key={log.id}
                            className="bg-red-950/50 border border-red-900/50 rounded p-3 mb-3"
                          >
                            <p className="text-red-400 text-sm">{log.content}</p>
                            <p className="text-[10px] text-red-600 mt-1">
                              {new Date(log.timestamp).toLocaleTimeString()}
                            </p>
                          </div>
                        ))
                    )}
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent value="raw" className="flex-1 m-0 overflow-hidden">
                <ScrollArea className="h-full">
                  <pre className="p-4 text-xs font-mono text-slate-400 whitespace-pre-wrap">
                    {JSON.stringify(debugLogs, null, 2)}
                  </pre>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}