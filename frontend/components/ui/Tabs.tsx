// Tabs.tsx
// Role: Tab navigation component

'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'

export interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: string
  onValueChange?: (value: string) => void
}

export const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
  ({ className, value, onValueChange, children, ...props }, ref) => {
    const [activeTab, setActiveTab] = React.useState(value || '')

    const handleTabChange = (newValue: string) => {
      setActiveTab(newValue)
      onValueChange?.(newValue)
    }

    return (
      <div ref={ref} className={cn('flex flex-col', className)} {...props}>
        {React.Children.map(children, (child) => {
          if (React.isValidElement(child) && child.type === TabsList) {
            return React.cloneElement(child as React.ReactElement<any>, {
              activeTab,
              onTabChange: handleTabChange,
            })
          }
          if (React.isValidElement(child) && child.type === TabsContent) {
            const contentProps = child.props as any
            if (contentProps.value === activeTab) {
              return child
            }
            return null
          }
          return child
        })}
      </div>
    )
  }
)
Tabs.displayName = 'Tabs'

export interface TabsListProps extends React.HTMLAttributes<HTMLDivElement> {
  activeTab?: string
  onTabChange?: (value: string) => void
}

export const TabsList = React.forwardRef<HTMLDivElement, TabsListProps>(
  ({ className, activeTab, onTabChange, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn('flex gap-1 border-b border-slate-700', className)}
        {...props}
      >
        {React.Children.map(children, (child) => {
          if (React.isValidElement(child) && child.type === TabsTrigger) {
            return React.cloneElement(child as React.ReactElement<any>, {
              isActive: child.props.value === activeTab,
              onClick: () => onTabChange?.(child.props.value),
            })
          }
          return child
        })}
      </div>
    )
  }
)
TabsList.displayName = 'TabsList'

export interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
  isActive?: boolean
}

export const TabsTrigger = React.forwardRef<HTMLButtonElement, TabsTriggerProps>(
  ({ className, isActive, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'px-3 py-1.5 text-sm font-medium transition-colors',
          isActive
            ? 'text-violet-400 border-b-2 border-violet-400'
            : 'text-slate-400 hover:text-slate-200',
          className
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)
TabsTrigger.displayName = 'TabsTrigger'

export interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
}

export const TabsContent = React.forwardRef<HTMLDivElement, TabsContentProps>(
  ({ className, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cn('flex-1 overflow-hidden', className)} {...props}>
        {children}
      </div>
    )
  }
)
TabsContent.displayName = 'TabsContent'