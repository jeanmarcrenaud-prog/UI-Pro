'use client'

import React from 'react'

export interface CardProps {
  children: React.ReactNode
  title?: string
  subtitle?: string
  isLoading?: boolean
  footer?: React.ReactNode
}

// Card component - wrapper with consistent padding, border radius, background
export function Card({ children, title, subtitle, isLoading = false, footer }: CardProps) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-md hover:shadow-lg transition-shadow">
      {isLoading ? (
        // Loading skeleton
        <div className="space-y-3 animate-pulse">
          <div className="h-6 bg-slate-800 rounded w-1/3" />
          <div className="h-4 bg-slate-800 rounded w-1/2" />
          <div className="h-4 bg-slate-800 rounded w-3/4" />
          <div className="h-4 bg-slate-800 rounded w-2/3" />
        </div>
      ) : title ? (
        // Card with header
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              {title && <h3 className="font-semibold text-white">{title}</h3>}
              {subtitle && <p className="text-sm text-slate-400 mt-1">{subtitle}</p>}
            </div>
          </div>

          <div className="bg-slate-950/30 rounded-lg p-4">
            {children}
          </div>

          {footer && <div className="border-t border-slate-800 pt-4 mt-4">{footer}</div>}
        </div>
      ) : (
        // Simple card
        <div className="space-y-3">
          {children}
        </div>
      )}
    </div>
  )
}
