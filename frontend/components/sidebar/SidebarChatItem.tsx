// sidebar/SidebarChatItem.tsx
// Role: Renders a single chat history entry in the sidebar

'use client'

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
        truncate
      "
    >
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
    </button>
  )
}
