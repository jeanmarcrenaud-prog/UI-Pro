'use client'

import React from 'react'

export type BadgeVariant = 'default' | 'success' | 'error' | 'warning' | 'info' | 'processing'

export interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  className?: string
  as?: React.ElementType
}

const variants: Record<BadgeVariant, string> = {
  default: 'bg-slate-800 text-slate-400',
  success: 'bg-green-900/30 text-green-400',
  error: 'bg-red-900/30 text-red-400',
  warning: 'bg-yellow-900/30 text-yellow-400',
  info: 'bg-blue-900/30 text-blue-400',
  processing: 'bg-violet-900/30 text-violet-400',
}

// Badge for status display - small pills with colors
export function BadgeComponent({
  children,
  variant = 'default',
  className,
  as: CustomElement = 'span',
}: BadgeProps) {
  return (
    <CustomElement
      className={`text-xs px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 font-medium whitespace-nowrap ${variants[variant]} ${className}`}
    >
      {children}
    </CustomElement>
  )
}
