// CommandPalette.tsx
// Role: Global command palette activated by Ctrl/Cmd+K

'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Command, Hash, Settings, Plus, Moon, Sun, Sparkles, FileText, X } from 'lucide-react'

interface CommandItem {
  id: string
  label: string
  icon: React.ReactNode
  action: () => void
  category: 'action' | 'navigation' | 'settings'
  shortcut?: string
}

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const { setTheme, theme, toggleFocusMode, setActiveTab } = useUIStore()
  const { clearMessages, startNewChat } = useChatStore()

  // Define commands
  const commands: CommandItem[] = useMemo(() => {
    const isMac = typeof navigator !== 'undefined' && navigator.platform.includes('Mac')
    const cmd = isMac ? '⌘' : 'Ctrl'
    
    return [
      // Actions
      {
        id: 'new-chat',
        label: 'New Chat',
        icon: <Plus className="w-4 h-4" />,
        action: () => { startNewChat(); onClose() },
        category: 'action' as const,
        shortcut: `${cmd}+N`,
      },
      {
        id: 'clear-chat',
        label: 'Clear Current Chat',
        icon: <X className="w-4 h-4" />,
        action: () => { clearMessages(); onClose() },
        category: 'action' as const,
      },
      
      // Navigation
      {
        id: 'go-chat',
        label: 'Go to Chat',
        icon: <FileText className="w-4 h-4" />,
        action: () => { setActiveTab('chat'); onClose() },
        category: 'navigation' as const,
        shortcut: 'Alt+1',
      },
      {
        id: 'go-history',
        label: 'Go to History',
        icon: <Hash className="w-4 h-4" />,
        action: () => { setActiveTab('history'); onClose() },
        category: 'navigation' as const,
        shortcut: 'Alt+2',
      },
      {
        id: 'go-settings',
        label: 'Go to Settings',
        icon: <Settings className="w-4 h-4" />,
        action: () => { setActiveTab('settings'); onClose() },
        category: 'navigation' as const,
        shortcut: 'Alt+3',
      },

      // Settings
      {
        id: 'toggle-theme',
        label: theme === 'dark' ? 'Switch to Light Mode' : theme === 'light' ? 'Switch to Purple Rain' : 'Switch to Dark Mode',
        icon: theme === 'dark' ? <Sun className="w-4 h-4" /> : theme === 'light' ? <Sparkles className="w-4 h-4" /> : <Moon className="w-4 h-4" />,
        action: () => {
        const next = theme === 'dark' ? 'light' : theme === 'light' ? 'purple-rain' : theme === 'purple-rain' ? 'pro' : 'dark'
        setTheme(next as 'dark' | 'light' | 'purple-rain' | 'pro')
          setTheme(next as 'dark' | 'light' | 'purple-rain')
          onClose()
        },
        category: 'settings' as const,
        shortcut: `${cmd}+Shift+D`,
      },
      {
        id: 'toggle-focus',
        label: 'Toggle Focus Mode',
        icon: <Search className="w-4 h-4" />,
        action: () => { toggleFocusMode(); onClose() },
        category: 'settings' as const,
        shortcut: `${cmd}+Shift+F`,
      },
    ]
  }, [clearMessages, startNewChat, theme, setTheme, toggleFocusMode, onClose])

  // Filter commands
  const filteredCommands = useMemo(() => {
    if (!query) return commands
    const q = query.toLowerCase()
    return commands.filter(c => c.label.toLowerCase().includes(q))
  }, [commands, query])

  // Group commands by category
  const groupedCommands = useMemo(() => {
    const groups: Record<string, CommandItem[]> = {}
    filteredCommands.forEach(cmd => {
      if (!groups[cmd.category]) groups[cmd.category] = []
      groups[cmd.category].push(cmd)
    })
    return Object.entries(groups)
  }, [filteredCommands])

  // Reset selected index when filtered results change
  useEffect(() => {
    if (selectedIndex >= filteredCommands.length && filteredCommands.length > 0) {
      setSelectedIndex(0)
    }
  }, [filteredCommands.length, selectedIndex])

  // Handle keyboard navigation
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex(i => (i + 1) % filteredCommands.length)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex(i => (i - 1 + filteredCommands.length) % filteredCommands.length)
      } else if (e.key === 'Enter') {
        e.preventDefault()
        filteredCommands[selectedIndex]?.action()
      } else if (e.key === 'Escape') {
        e.preventDefault()
        if (query) {
          setQuery('')
        } else {
          onClose()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, filteredCommands, selectedIndex, onClose, query])

  // Reset when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, y: -20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
          onClick={e => e.stopPropagation()}
        >
          {/* Search Input */}
          <div className="flex items-center gap-3 px-4 py-4 border-b border-slate-800">
            <Search className="w-5 h-5 text-slate-500" />
            <input
              type="text"
              placeholder="Type a command..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none text-lg"
              autoFocus
            />
            <kbd className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded">Esc</kbd>
          </div>

          {/* Commands List */}
          <div className="max-h-[300px] overflow-y-auto py-2">
            {filteredCommands.length === 0 ? (
              <div className="px-4 py-8 text-center text-slate-500">
                No commands found
              </div>
            ) : (
              groupedCommands.map(([category, cmds]) => (
                <div key={category}>
                  <div className="px-4 py-2 text-xs font-medium text-slate-500 uppercase tracking-wider">
                    {category}
                  </div>
                  {cmds.map((cmd) => {
                    // Find global index for selection tracking
                    const globalIndex = filteredCommands.findIndex(c => c.id === cmd.id)
                    return (
                      <button
                        key={cmd.id}
                        onClick={cmd.action}
                        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${
                          globalIndex === selectedIndex 
                            ? 'bg-violet-600 text-white' 
                            : 'text-slate-300 hover:bg-slate-800'
                        }`}
                      >
                        <span className="opacity-70">{cmd.icon}</span>
                        <span className="flex-1">{cmd.label}</span>
                        {cmd.shortcut && (
                          <kbd className={`text-xs px-2 py-0.5 rounded ${
                            globalIndex === selectedIndex 
                              ? 'bg-white/20' 
                              : 'bg-slate-800'
                          }`}>
                            {cmd.shortcut}
                          </kbd>
                        )}
                      </button>
                    )
                  })}
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <span><kbd>↑↓</kbd> navigate</span>
            <span><kbd>↵</kbd> select</span>
            <span><kbd>esc</kbd> close</span>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

// Hook for keyboard shortcuts
export function useKeyboardShortcuts() {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const { toggleFocusMode } = useUIStore()
  const { startNewChat } = useChatStore()

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + K - Command Palette
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen(true)
      }
      // Ctrl/Cmd + Shift + F - Focus mode
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
        e.preventDefault()
        toggleFocusMode()
      }
      // Ctrl/Cmd + Enter - Send message
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        // Handled by ChatInput
      }
      // Ctrl/Cmd + N - New chat
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        startNewChat()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [toggleFocusMode, startNewChat])

  return { paletteOpen, setPaletteOpen }
}