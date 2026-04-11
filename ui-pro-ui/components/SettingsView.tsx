'use client'

// Settings View

import { useUIStore } from '@/lib/stores/uiStore'
import { modelDiscovery } from '@/services/modelDiscovery'
import { motion } from 'framer-motion'

export function SettingsView() {
  const { availableModels, selectedModel, setSelectedModel } = useUIStore()

  const handleRefreshModels = async () => {
    await modelDiscovery.discover()
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex-1 p-6 overflow-y-auto"
    >
      <h2 className="text-xl font-semibold text-white mb-6">Settings</h2>

      {/* Model Settings */}
      <div className="mb-8">
        <h3 className="text-sm font-medium text-slate-400 mb-3">Models</h3>
        <div className="bg-slate-800 rounded-xl p-4 space-y-4">
          <div>
            <label className="text-xs text-slate-400 mb-2 block">Default Model</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2"
            >
              {availableModels.map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>
          
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white">Available Models</p>
              <p className="text-xs text-slate-400">{availableModels.length} models discovered</p>
            </div>
            <button
              onClick={handleRefreshModels}
              className="bg-violet-600 hover:bg-violet-700 text-white text-sm px-4 py-2 rounded-lg"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Backend Settings */}
      <div className="mb-8">
        <h3 className="text-sm font-medium text-slate-400 mb-3">Backends</h3>
        <div className="bg-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white">Ollama</p>
              <p className="text-xs text-slate-400">http://localhost:11434</p>
            </div>
            <span className="text-xs text-green-400">● Active</span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white">LM Studio</p>
              <p className="text-xs text-slate-400">http://localhost:1234</p>
            </div>
            <span className="text-xs text-slate-500">○ Not running</span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-white">llama.cpp</p>
              <p className="text-xs text-slate-400">http://localhost:8080</p>
            </div>
            <span className="text-xs text-slate-500">○ Disabled</span>
          </div>
        </div>
      </div>

      {/* About */}
      <div>
        <h3 className="text-sm font-medium text-slate-400 mb-3">About</h3>
        <div className="bg-slate-800 rounded-xl p-4">
          <p className="text-sm text-white">UI-Pro v1.0</p>
          <p className="text-xs text-slate-400 mt-1">AI Agent Orchestration System</p>
          <p className="text-xs text-slate-500 mt-2">Powered by Ollama + Next.js</p>
        </div>
      </div>
    </motion.div>
  )
}