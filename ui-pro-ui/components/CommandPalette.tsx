// CommandPalette.tsx
// Role: Global command palette activated by Ctrl/Cmd+K

'use client'

import { useState, useEffect, useMemo } from 'react'
import { useUIStore } from '@/lib/stores/uiStore'
import { useChatStore } from '@/lib/stores/chatStore'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Command, Hash, Settings, Plus, Moon, Sun, FileText, X } from 'lucide-react'

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
  const { setTheme, theme, toggleFocusMode } = useUIStore()
  const { clearMessages } = useChatStore()

  // Define commands
  const commands: CommandItem[] = useMemo(() => [
    // Actions
    {
      id: 'new-chat',
      label: 'New Chat',
      icon: <Plus className="w-4 h-4" />,
      action: () => { clearMessages(); onClose() },
      category: 'action',
      shortcut: 'Ctrl+N',
    },
    {
      id: 'clear-chat',
      label: 'Clear Current Chat',
      icon: <X className="w-4 h-4" />,
      action: () => { clearMessages(); onClose() },
      category: 'action',
    },
    
    // Navigation
    {
      id: 'go-chat',
      label: 'Go to Chat',
      icon: <FileText className="w-4 h-4" />,
      action: () => { onClose() },
      category: 'navigation',
      shortcut: 'Alt+1',
    },
    {
      id: 'go-history',
      label: 'Go to History',
      icon: <Hash className="w-4 h-4" />,
      action: () => { onClose() },
      category: 'navigation',
      shortcut: 'Alt+2',
    },
    {
      id: 'go-settings',
      label: 'Go to Settings',
      icon: <Settings className="w-4 h-4" />,
      action: () => { onClose() },
      category: 'navigation',
      shortcut: 'Alt+3',
    },

    // Settings
    {
      id: 'toggle-theme',
      label: theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode',
      icon: theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />,
      action: () => { setTheme(theme === 'dark' ? 'light' : 'dark'); onClose() },
      category: 'settings',
      shortcut: 'Ctrl+Shift+D',
    },
    {
      id: 'toggle-focus',
      label: 'Toggle Focus Mode',
      icon: <Search className="w-4 h-4" />,
      action: () => { toggleFocusMode(); onClose() },
      category: 'settings',
      shortcut: 'Ctrl+Shift+F',
    },
  ], [clearMessages, theme, setTheme, toggleFocusMode, onClose])

  // Filter commands
  const filteredCommands = useMemo(() => {
    if (!query) return commands
    const q = query.toLowerCase()
    return commands.filter(c => c.label.toLowerCase().includes(q))
  }, [commands, query])

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
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, filteredCommands, selectedIndex, onClose])

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
              filteredCommands.map((cmd, i) => (
                <button
                  key={cmd.id}
                  onClick={cmd.action}
                  className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${
                    i === selectedIndex 
                      ? 'bg-violet-600 text-white' 
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span className="opacity-70">{cmd.icon}</span>
                  <span className="flex-1">{cmd.label}</span>
                  {cmd.shortcut && (
                    <kbd className={`text-xs px-2 py-0.5 rounded ${
                      i === selectedIndex 
                        ? 'bg-white/20' 
                        : 'bg-slate-800'
                    }`}>
                      {cmd.shortcut}
                    </kbd>
                  )}
                </button>
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
        useChatStore.getState().clearMessages()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [toggleFocusMode])

  return { paletteOpen, setPaletteOpen }
}