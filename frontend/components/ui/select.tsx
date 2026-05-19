// Select.tsx
// Role: Styled dropdown select with label, error state, empty message and custom SVG caret

'use client'

import React, { useRef } from 'react'

export interface SelectComponentProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  emptyMessage?: string
}

export function SelectComponent({
  label,
  error,
  emptyMessage = 'No models available',
  className,
  children,
  ...props
}: SelectComponentProps) {
  // Select with bg-slate-800, border-slate-700, text-slate-200
  // Focus ring violet-500
  // Empty message when no options
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm text-slate-400 font-medium">
          {label}
        </label>
      )}
      <select
        className={`flex flex-col gap-1.5 w-full bg-slate-800 border text-slate-200 text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${error ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : 'border-slate-700'} ${className || ''}`}
        style={{
          borderColor: error ? '#ef4444' : '#334155',
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='12' height='12' fill='${error ? '#fef2f2' : '#cbd5f5'}' viewBox='0 0 16 16' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath fill-rule='evenodd' d='M1.204 5.962.166 4.814a.995.995 0 01.277-1.337l18.005-7.335a.995.995 0 011.214.317l-10.924 10.924a.995.995 0 01-1.213.317L1.204 5.962zm8.049 8.237L.228 6.264a.995.995 0 01.359-1.457l14.996-6.355a.995.995 0 011.345.54L8.999 14.2z' clip-rule='evenodd'/%3E%3C/svg%3E") bottom right no-repeat`,
        }}
        {...props}
      >
        {children}
      </select>
      {(error || label) && (
        <div className="flex items-center gap-1 text-xs">
          {error && <span className="text-red-400 flex-shrink-0">*</span>}
          <span className={error ? 'text-red-400' : 'text-slate-500'}>{error}</span>
        </div>
      )}
    </div>
  )
}
