// HistoryBatchActions.tsx
// Role: Batch actions toolbar for selected chats

'use client'

import { Download, Archive, Trash2, Pin } from 'lucide-react'

interface HistoryBatchActionsProps {
  selectedCount: number
  totalCount: number
  onExport: () => void
  onArchive: () => void
  onPin: () => void
  onDelete: () => void
}

export function HistoryBatchActions({ selectedCount, totalCount, onExport, onArchive, onPin, onDelete }: HistoryBatchActionsProps) {
  if (selectedCount === 0) return null

  return (
    <div className="mb-3 p-3 bg-red-950/30 border border-red-800/50 rounded-lg flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-lg font-semibold text-red-400">
          {selectedCount}
          <span className="text-red-600">/{totalCount}</span>
        </span>
        <span className="text-sm text-red-300/70">selected</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onPin}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-violet-700 hover:bg-violet-600 rounded-lg text-white"
        >
          <Pin className="w-4 h-4" />
          Pin
        </button>
        <button
          onClick={onExport}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 rounded-lg text-white"
        >
          <Download className="w-4 h-4" />
          Export
        </button>
        <button
          onClick={onArchive}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 rounded-lg text-white"
        >
          <Archive className="w-4 h-4" />
          Archive
        </button>
        <button
          onClick={onDelete}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-red-600 hover:bg-red-500 rounded-lg text-white font-medium"
        >
          <Trash2 className="w-4 h-4" />
          Delete
        </button>
      </div>
    </div>
  )
}