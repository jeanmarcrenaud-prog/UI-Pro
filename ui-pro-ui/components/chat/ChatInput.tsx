'use client'

// ChatInput - Text input for chat messages

import { useState, type FormEvent } from 'react'

interface ChatInputProps {
  onSend: (message: string) => void
  isLoading?: boolean
}

export function ChatInput({ onSend, isLoading = false }: ChatInputProps) {
  const [input, setInput] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    onSend(input.trim())
    setInput('')
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full gap-2">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={isLoading ? 'Processing...' : 'Type your message...'}
        disabled={isLoading}
        className="flex-1 rounded-lg border border-gray-300 px-4 py-2 
          dark:border-gray-700 dark:bg-gray-800
          focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <button
        type="submit"
        disabled={isLoading || !input.trim()}
        className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white
          hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? '...' : 'Send'}
      </button>
    </form>
  )
}