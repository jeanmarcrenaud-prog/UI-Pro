// HistoryView.tsx
// Role: History page with search, filters, grouping, tags, archive, pin, rename, export and multi-select

'use client'

import { useState, useMemo, useCallback } from 'react'
import { useChatStore } from '@/lib/stores/chatStore'
import { useUIStore } from '@/lib/stores/uiStore'
import { useI18n } from '@/lib/i18n'
import { motion } from 'framer-motion'
import { FileText, Calendar } from 'lucide-react'

// Sub-components
import { HistoryItem } from './chat/HistoryItem'
import { HistoryFilters } from './chat/HistoryFilters'
import { HistoryBatchActions } from './chat/HistoryBatchActions'

import type { SortOption, DateGroup } from './chat/HistoryFilters'

// Date grouping logic
function getDateGroup(dateStr: string): DateGroup {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / 86400000)
  
  if (diffDays === 0) return 'today'
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return 'this_week'
  return 'older'
}

function getDateGroupLabel(group: DateGroup): string {
  const labels: Record<DateGroup, string> = {
    today: "Today",
    yesterday: "Yesterday",
    this_week: "This Week",
    older: "Older",
  }
  return labels[group]
}

interface HistoryViewProps {
  onSelectChat?: (chatId: string) => void
  onClose?: () => void
}

export function HistoryView({ onSelectChat, onClose }: HistoryViewProps) {
  const { 
    history, loadChat, deleteChat, renameChat, archiveChat, unarchiveChat, 
    togglePinChat, addTagToChat, removeTagFromChat 
  } = useChatStore()
  const { selectedModel } = useUIStore()
  
  // Edit state
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  
  // Filter state
  const [showArchived, setShowArchived] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState<SortOption>('date_desc')
  const [filterModel, setFilterModel] = useState<string>('')
  const [filterTag, setFilterTag] = useState<string>('')
  const [showFilters, setShowFilters] = useState(false)
  
  // Multi-select state
  const [selectedChats, setSelectedChats] = useState<Set<string>>(new Set())
  const [selectMode, setSelectMode] = useState(false)
  
  const { t } = useI18n()

  // --- Computed (before actions that depend on them) ---
  
  const allTags = useMemo(() => {
    const tags = new Set<string>()
    history.forEach(c => c.tags?.forEach(tag => tags.add(tag)))
    return Array.from(tags).sort()
  }, [history])

  const filteredHistory = useMemo(() => {
    let chats = [...history]
    
    if (!showArchived) chats = chats.filter(c => !c.archived)
    
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      chats = chats.filter(c => 
        c.title.toLowerCase().includes(q) || 
        c.messages?.some(m => m.content?.toLowerCase().includes(q))
      )
    }
    
    if (filterTag) chats = chats.filter(c => c.tags?.includes(filterTag))
    
    return chats.sort((a, b) => {
      if (a.isPinned && !b.isPinned) return -1
      if (!a.isPinned && b.isPinned) return 1
      
      switch (sortBy) {
        case 'date_desc': return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        case 'date_asc': return new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime()
        case 'title': return a.title.localeCompare(b.title)
        default: return 0
      }
    })
  }, [history, showArchived, searchQuery, sortBy, filterTag])

  const groupedHistory = useMemo(() => {
    const groups: Record<DateGroup, typeof filteredHistory> = { today: [], yesterday: [], this_week: [], older: [] }
    filteredHistory.forEach(chat => groups[getDateGroup(chat.updatedAt)].push(chat))
    return groups
  }, [filteredHistory])

  // --- Actions ---
  
  const toggleSelect = useCallback((chatId: string) => {
    setSelectedChats(prev => {
      const next = new Set(prev)
      next.has(chatId) ? next.delete(chatId) : next.add(chatId)
      return next
    })
  }, [])

  const selectAll = useCallback(() => {
    setSelectedChats(prev => 
      prev.size === filteredHistory.length 
        ? new Set() 
        : new Set(filteredHistory.map(c => c.id))
    )
  }, [filteredHistory])

  const deleteSelected = useCallback(() => {
    selectedChats.forEach(id => deleteChat(id))
    setSelectedChats(new Set())
    setSelectMode(false)
  }, [selectedChats])

  const archiveSelected = useCallback(() => {
    selectedChats.forEach(id => archiveChat(id))
    setSelectedChats(new Set())
    setSelectMode(false)
  }, [selectedChats])

  const pinSelected = useCallback(() => {
    selectedChats.forEach(id => togglePinChat(id))
    setSelectedChats(new Set())
    setSelectMode(false)
  }, [selectedChats])

  const exportSelected = useCallback(() => {
    let combinedMd = '# UI-Pro Conversations Export\n\n---\n\n'
    filteredHistory
      .filter(c => selectedChats.has(c.id))
      .forEach(chat => {
        combinedMd += `## ${chat.title}\n\n`
        combinedMd += `*${new Date(chat.updatedAt).toLocaleString()}*\n\n---\n\n`
        chat.messages?.forEach(msg => {
          const role = msg.role === 'user' ? '**User**' : '**Assistant**'
          combinedMd += `${role}: ${msg.content || ''}\n\n`
        })
        combinedMd += '---\n\n'
      })
    
    const blob = new Blob([combinedMd], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ui-pro-export-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
    setSelectedChats(new Set())
    setSelectMode(false)
  }, [filteredHistory, selectedChats])

  // --- Handlers ---
  
  const handleSelect = useCallback((chatId: string) => {
    loadChat(chatId)
    onSelectChat?.(chatId)
  }, [loadChat, onSelectChat])

  const handleDelete = useCallback((chatId: string) => {
    if (confirmDelete === chatId) {
      deleteChat(chatId)
      setConfirmDelete(null)
    } else {
      setConfirmDelete(chatId)
    }
  }, [confirmDelete, deleteChat])

  const handleRename = useCallback((chatId: string) => {
    if (editTitle.trim()) renameChat(chatId, editTitle.trim())
    setEditingId(null)
  }, [editTitle, renameChat])

  const handleArchive = useCallback((chatId: string) => {
    const chat = history.find(c => c.id === chatId)
    chat?.archived ? unarchiveChat(chatId) : archiveChat(chatId)
  }, [history, archiveChat, unarchiveChat])

  const handlePin = useCallback((chatId: string) => {
    togglePinChat(chatId)
  }, [togglePinChat])

  const handleExport = useCallback((chatId: string) => {
    const chat = history.find(c => c.id === chatId)
    if (!chat) return
    
    let md = `# ${chat.title}\n\n---\n\n`
    chat.messages?.forEach(msg => {
      const role = msg.role === 'user' ? 'User' : 'Assistant'
      md += `${role}: ${msg.content || ''}\n\n`
    })
    
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${chat.title.replace(/[^a-z0-9]/gi, '_')}.md`
    a.click()
    URL.revokeObjectURL(url)
  }, [history])

  // --- Render ---
  
  const dateGroups: DateGroup[] = ['today', 'yesterday', 'this_week', 'older']

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Filters & Controls */}
      <div className="p-4 border-b border-slate-800">
        <HistoryFilters
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          showFilters={showFilters}
          onToggleFilters={() => setShowFilters(!showFilters)}
          sortBy={sortBy}
          onSortChange={setSortBy}
          showArchived={showArchived}
          onToggleArchived={setShowArchived}
          selectMode={selectMode}
          onToggleSelectMode={() => setSelectMode(!selectMode)}
          selectedCount={selectedChats.size}
          totalCount={filteredHistory.length}
          onSelectAll={selectAll}
          allTags={allTags}
          filterTag={filterTag}
          onFilterTagChange={setFilterTag}
        />
      </div>

      {/* Batch Actions */}
      <div className="px-4">
        <HistoryBatchActions
          selectedCount={selectedChats.size}
          totalCount={filteredHistory.length}
          onExport={exportSelected}
          onArchive={archiveSelected}
          onPin={pinSelected}
          onDelete={deleteSelected}
        />
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto">
        {filteredHistory.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No conversations yet</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800">
            {dateGroups.map(group => {
              const chats = groupedHistory[group]
              if (chats.length === 0) return null
              
              return (
                <div key={group}>
                  <div className="px-4 py-2 sticky top-0 bg-slate-900/95 backdrop-blur-sm border-b border-slate-800">
                    <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider flex items-center gap-2">
                      <Calendar className="w-3 h-3" />
                      {getDateGroupLabel(group)}
                      <span className="text-slate-600">({chats.length})</span>
                    </h3>
                  </div>
                  
                  {chats.map((chat, index) => (
                    <HistoryItem
                      key={chat.id}
                      chat={chat}
                      isSelected={selectedChats.has(chat.id)}
                      selectMode={selectMode}
                      editingId={editingId}
                      editTitle={editTitle}
                      filterTag={filterTag}
                      onSelect={() => handleSelect(chat.id)}
                      onToggleSelect={() => toggleSelect(chat.id)}
                      onRename={() => handleRename(chat.id)}
                      onEditTitle={setEditTitle}
                      onCancelEdit={() => setEditingId(null)}
                      onArchive={() => handleArchive(chat.id)}
                      onPin={() => handlePin(chat.id)}
                      onExport={() => handleExport(chat.id)}
                      onDelete={() => handleDelete(chat.id)}
                      onSetFilterTag={setFilterTag}
                    />
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}