'use client'

import React from 'react'

export function TypingIndicator() {
  return (
    <div className="flex gap-1.5 px-4 py-2 bg-slate-800/50 rounded-full">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
          style={{
            animationDelay: `${i * 150}ms`,
            animationDuration: '1s',
            display: 'inline-block',
          }}
        />
      ))}
    </div>
  )
}
