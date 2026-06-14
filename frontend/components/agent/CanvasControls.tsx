// components/agent/CanvasControls.tsx
// Toolbar controls for the Agent Canvas: palette toggle, export, split view
// (Zoom/pan are handled by the built-in React Flow Controls)

'use client'

import { Palette, Image, FileJson, Columns } from 'lucide-react'

interface CanvasControlsProps {
  onExportPng: () => void
  onExportJson: () => void
  onSplitView?: () => void
  splitViewActive?: boolean
  showSplitView?: boolean
  paletteOpen?: boolean
  onTogglePalette?: () => void
}

export function CanvasControls({
  onExportPng,
  onExportJson,
  onSplitView,
  splitViewActive = false,
  showSplitView = false,
  paletteOpen = false,
  onTogglePalette,
}: CanvasControlsProps) {
  const btnClass =
    'p-1.5 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed'

  return (
    <div className="flex items-center gap-1 px-3 py-2 border-b border-slate-700/50 bg-slate-900/50">
      {/* Palette toggle */}
      <button
        onClick={onTogglePalette}
        className={`${btnClass} ${paletteOpen ? '!text-violet-400 !bg-violet-500/20' : ''}`}
        title="Toggle node palette"
      >
        <Palette size={14} />
      </button>

      <div className="w-px h-5 bg-slate-700 mx-1" />

      {/* Export */}
      <button onClick={onExportPng} className={btnClass} title="Export as PNG">
        <Image size={14} />
      </button>
      <button onClick={onExportJson} className={btnClass} title="Export as JSON">
        <FileJson size={14} />
      </button>

      {showSplitView && onSplitView && (
        <>
          <div className="w-px h-5 bg-slate-700 mx-1" />
          <button
            onClick={onSplitView}
            className={`${btnClass} ${splitViewActive ? '!text-violet-400 !bg-violet-500/20' : ''}`}
            title="Toggle split view"
          >
            <Columns size={14} />
          </button>
        </>
      )}
    </div>
  )
}
