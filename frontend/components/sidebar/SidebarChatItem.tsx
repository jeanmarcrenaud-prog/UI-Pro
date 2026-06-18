// sidebar/SidebarChatItem.tsx
// Role: Renders a single chat history entry in the sidebar with task type detection

'use client'

import { useMemo } from 'react'
import { Terminal, FileCode, Code2, Braces, Shell, Database, Globe, Puzzle } from 'lucide-react'

// Detect task type from title/content keywords
const TASK_ICONS: Array<{ patterns: RegExp[]; icon: React.ElementType; color: string }> = [
  { patterns: [/python/i, /\.py\b/i, /pytest/i, /django/i, /fastapi/i, /flask/i], icon: Code2, color: 'text-blue-400' },
  { patterns: [/powershell/i, /\.ps1/i, /pwsh/i], icon: Terminal, color: 'text-blue-300' },
  { patterns: [/javascript/i, /\.js\b/i, /node/i, /react/i, /vue/i, /angular/i], icon: FileCode, color: 'text-yellow-400' },
  { patterns: [/typescript/i, /\.ts\b/i, /\.tsx/i], icon: Braces, color: 'text-blue-500' },
  { patterns: [/bash/i, /shell/i, /sh\b/i, /zsh/i], icon: Shell, color: 'text-emerald-400' },
  { patterns: [/sql/i, /database/i, /postgres/i, /mysql/i, /query/i], icon: Database, color: 'text-orange-400' },
  { patterns: [/api/i, /rest/i, /graphql/i, /endpoint/i], icon: Globe, color: 'text-violet-400' },
]

function getTaskIcon(title: string): { icon: React.ElementType; color: string } {
  for (const entry of TASK_ICONS) {
    if (entry.patterns.some(p => p.test(title))) {
      return { icon: entry.icon, color: entry.color }
    }
  }
  return { icon: Puzzle, color: 'text-slate-500' }
}

export function SidebarChatItem({
  chat,
  onClick
}: {
  chat: any
  onClick: () => void
}) {
  const updatedAt = new Date(chat.updatedAt)
  const dateStr = updatedAt.toLocaleDateString()
  const timeStr = updatedAt.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })

  const taskInfo = useMemo(() => getTaskIcon(chat.title || ''), [chat.title])
  const Icon = taskInfo.icon

  return (
    <button
      onClick={onClick}
      className="
        w-full 
        text-left 
        px-3 
        py-2.5 
        rounded-xl 
        text-sm 
        text-slate-400 
        hover:bg-slate-800/50 
        hover:text-slate-200 
        transition-all duration-150 
        group
      "
    >
      <div className="flex items-start gap-2.5">
        <div className={`mt-0.5 shrink-0 ${taskInfo.color} opacity-60 group-hover:opacity-100 transition-opacity`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div
            className="
              truncate 
              font-medium 
              group-hover:text-slate-200
              transition-colors duration-150
            "
            title={chat.title}
          >
            {chat.title}
          </div>
          <div className="text-[10px] text-slate-600 mt-0.5">
            {dateStr} • {timeStr}
          </div>
        </div>
      </div>
    </button>
  )
}
