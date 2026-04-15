'use client'

import React from 'react'

export interface InputComponentProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
}

export function InputComponent({
  label,
  error,
  helperText,
  className,
  ...props
}: InputComponentProps) {
  // Input with slate-900 background, slate-700 border, rounded-xl
  // Focus ring uses violet-500 for accent
  // Error state uses red border/indicator
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm text-slate-400 font-medium">
          {label}
        </label>
      )}
      <input
        className={`
          w-full
          bg-slate-900
          border
          rounded-xl
          px-4
          py-3
          text-white
          placeholder-slate-500
          transition-colors
          disabled:opacity-50
          disabled:cursor-not-allowed
          focus:outline-none
          focus:ring-2
          focus:ring-violet-500/20
          focus:border-violet-500
          ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : 'border-slate-700'}
          ${className}
        `}
        style={{
          borderColor: error ? '#ef4444' : '#334155',
        }}
        {...props}
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
