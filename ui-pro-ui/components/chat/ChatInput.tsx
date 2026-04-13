'use client'

import { useState } from 'react'

interface ChatInputProps {
  onSend: (message: string) => void
  isLoading?: boolean
}

export default function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [value, setValue] = useState('')

  const handleSend = () => {
    if (!value.trim() || isLoading) return
    onSend(value)
    setValue('')
  }

  return (
    <div className="flex items-center gap-2 bg-[#0f172a] p-2 rounded-xl border border-gray-700">
      <textarea
        className="flex-1 bg-transparent outline-none text-white px-3 resize-none"
        placeholder="Describe your task..."
        value={value}
        rows={1}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            handleSend()
          }
        }}
      />

      <button
        disabled={isLoading}
        className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-4 py-2 rounded-lg"
        onClick={handleSend}
      >
        ➤
      </button>
    </div>
  )
}
