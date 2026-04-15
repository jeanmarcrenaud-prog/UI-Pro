'use client'

import React from 'react'

export interface TextareaComponentProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  helperText?: string
  rows?: number
}

export function TextareaComponent({
  label,
  error,
  helperText,
  rows = 4,
  className,
  ...props
}: TextareaComponentProps) {
  // Textarea with rounded-xl, bg-slate-900, border-slate-700
  // Auto-resize on input, focus ring violet-500
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm text-slate-400 font-medium">
          {label}
        </label>
      )}
      <textarea
        className={`
          w-full
          bg-slate-900
          border
          rounded-xl
          px-4
          py-3
          text-white
          placeholder-slate-500
          outline-none
          transition-colors
          disabled:opacity-50
          disabled:cursor-not-allowed
          resize-none
          focus:ring-2
          focus:ring-violet-500/20
          focus:border-violet-500
          ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : 'border-slate-700'}
          ${className}
        `}
        {...props}
        style={{
          borderColor: error ? '#ef4444' : '#334155',
        }}
      />
      {(error || helperText) && (
        <div className="flex items-center gap-1 text-xs">
          {error && <span className="text-red-400 flex-shrink-0">*</span>}
          <span className={error ? 'text-red-400' : 'text-slate-500'}>{error || helperText}</span>
        </div>
      )}
    </div>
  )
}
