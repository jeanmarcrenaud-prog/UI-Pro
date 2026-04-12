'use client'

// ChatInput - Text input for chat messages

import { useState, type FormEvent } from 'react'

interface ChatInputProps {
  onSend: (message: string) => void
  isLoading?: boolean
}

export default function ChatInput({ onSend }) {
  const [value, setValue] = useState("")

  return (
    <div className="flex items-center gap-2 bg-[#0f172a] p-2 rounded-xl border border-gray-700">
      <input
        className="flex-1 bg-transparent outline-none text-white px-3"
        placeholder="Describe your task..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            onSend(value)
            setValue("")
          }
        }}
      />

      <button
        className="bg-purple-600 hover:bg-purple-700 transition px-4 py-2 rounded-lg"
        onClick={() => {
          onSend(value)
          setValue("")
        }}
      >
        ➤
      </button>
    </div>
  )
}