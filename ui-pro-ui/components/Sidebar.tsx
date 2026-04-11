'use client'

// UI-Pro Sidebar - ChatGPT quality

import { useState } from 'react'

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
  onNewChat?: () => void
}

const tabs = [
  { id: 'chat', label: 'Chat', icon: '💬' },
  { id: 'history', label: 'History', icon: '📜' },
  { id: 'settings', label: 'Settings', icon: '⚙️' },
]

const models = [
  { id: 'gemma4', label: 'Gemma 4' },
  { id: 'qwen-coder', label: 'Qwen Coder' },
  { id: 'mistral', label: 'Mistral' },
  { id: 'deepseek', label: 'DeepSeek' },
]

export function Sidebar({ activeTab, onTabChange, onNewChat }: SidebarProps) {
  const [selectedModel, setSelectedModel] = useState('gemma4')
  const [chats] = useState([
    { id: '1', title: 'Analysis project', time: '2h ago' },
    { id: '2', title: 'Code review', time: '5h ago' },
  ])

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col">
      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full bg-violet-600 hover:bg-violet-700 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors flex items-center gap-2"
        >
          <span>+</span> New Chat
        </button>
      </div>

      {/* Model Selector */}
      <div className="px-3 pb-3">
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          className="w-full bg-slate-800 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-violet-500"
        >
          {models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.label}
            </option>
          ))}
        </select>
      </div>

      {/* Navigation */}
      <nav className="px-2 space-y-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
              activeTab === tab.id
                ? 'bg-slate-800 text-white'
                : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
            }`}
          >
            <span className="mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto mt-4 px-2">
        <div className="text-xs text-slate-500 px-3 py-2">Recent Chats</div>
        {chats.map((chat) => (
          <button
            key={chat.id}
            className="w-full text-left px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-slate-800/50 hover:text-white transition-colors"
          >
            <div className="truncate">{chat.title}</div>
            <div className="text-xs text-slate-600">{chat.time}</div>
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800 text-xs text-slate-500">
        <div>UI-Pro v1.0</div>
        <div className="text-slate-600 mt-1">Powered by Ollama</div>
      </div>
    </aside>
  )
}