// HistoryItem.tsx
// Role: Single chat item in history list

'use client'

import { motion } from 'framer-motion'
import { Pin, Archive, Clock, Check, X, Download, Edit2 } from 'lucide-react'
import type { ChatHistoryItem } from '@/lib/types'

interface HistoryItemProps {
  chat: ChatHistoryItem
  isSelected: boolean
  selectMode: boolean
  editingId: string | null
  editTitle: string
  filterTag: string
  onSelect: () => void
  onToggleSelect: () => void
  onRename: () => void
  onEditTitle: (title: string) => void
  onCancelEdit: () => void
  onArchive: () => void
  onPin: () => void
  onExport: () => void
  onDelete: () => void
  onSetFilterTag: (tag: string) => void
}

export function HistoryItem({
  chat,
  isSelected,
  selectMode,
  editingId,
  editTitle,
  filterTag,
  onSelect,
  onToggleSelect,
  onRename,
  onEditTitle,
  onCancelEdit,
  onArchive,
  onPin,
  onExport,
  onDelete,
  onSetFilterTag,
}: HistoryItemProps) {
  const msgCount = chat.messages?.length ?? 0
  const previewMessage = chat.messages?.find(m => m.role === 'assistant')
  const preview = previewMessage?.content?.slice(0, 200) || '...'

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)
    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-4 hover:bg-slate-800/30 transition-colors cursor-pointer group ${isSelected ? 'bg-violet-900/20' : ''}`}
      onClick={() => selectMode ? onToggleSelect() : onSelect()}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Checkbox */}
        {selectMode && (
          <div className="flex-shrink-0 mt-1" onClick={(e) => { e.stopPropagation(); onToggleSelect() }}>
            <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
              isSelected ? 'bg-violet-500 border-violet-500' : 'border-slate-600'
            }`}>
              {isSelected && <Check className="w-3 h-3 text-white" />}
            </div>
          </div>
        )}
        
        <div className={`flex-1 min-w-0 ${selectMode ? 'ml-2' : ''}`}>
          {/* Title */}
          {editingId === chat.id ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={editTitle}
                onChange={(e) => onEditTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onRename()
                  if (e.key === 'Escape') onCancelEdit()
                }}
                className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-white"
                autoFocus
              />
              <button onClick={onRename} className="text-emerald-400"><Check className="w-4 h-4" /></button>
              <button onClick={onCancelEdit} className="text-slate-400"><X className="w-4 h-4" /></button>
            </div>
          ) : (
            <h3 className="font-medium text-white truncate flex items-center gap-2">
              {chat.isPinned && <Pin className="w-4 h-4 text-violet-400 fill-current" />}
              {chat.archived && <Archive className="w-4 h-4 text-slate-500" />}
              {chat.title}
            </h3>
          )}
          
          {/* Meta */}
          <p className="text-xs text-slate-500 mt-1 flex items-center gap-2">
            <Clock className="w-3 h-3" />
            {msgCount} msg{msgCount !== 1 ? 's' : ''} • {formatTime(chat.updatedAt)}
          </p>
          
          {/* Tags */}
          {chat.tags && chat.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {chat.tags.map(tag => (
                <button
                  key={tag}
                  onClick={(e) => { e.stopPropagation(); onSetFilterTag(filterTag === tag ? '' : tag) }}
                  className={`text-xs px-2 py-0.5 rounded-full transition-colors ${
                    filterTag === tag ? 'bg-violet-500 text-white' : 'bg-violet-600/30 text-violet-300 hover:bg-violet-600/50'
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          )}
          
          {/* Preview */}
          {msgCount > 0 && <p className="text-sm text-slate-500 mt-2 line-clamp-4">{preview}</p>}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={(e) => { e.stopPropagation(); onPin() }} className={`p-2 rounded hover:bg-slate-700 ${chat.isPinned ? 'text-violet-400' : 'text-slate-600 opacity-0 group-hover:opacity-100'}`} title="Pin">
            <Pin className={`w-4 h-4 ${chat.isPinned ? 'fill-current' : ''}`} />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onEditTitle(chat.title); onSelect(); }} className="p-2 text-slate-600 hover:text-white hover:bg-slate-700 rounded opacity-0 group-hover:opacity-100" title="Rename">
            <Edit2 className="w-4 h-4" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onArchive() }} className="p-2 text-slate-600 hover:text-white hover:bg-slate-700 rounded opacity-0 group-hover:opacity-100" title={chat.archived ? 'Unarchive' : 'Archive'}>
            <Archive className="w-4 h-4" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onExport() }} className="p-2 text-slate-600 hover:text-white hover:bg-slate-700 rounded opacity-0 group-hover:opacity-100" title="Export MD">
            <Download className="w-4 h-4" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onDelete() }} className="p-2 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100" title="Delete">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </motion.div>
  )
}