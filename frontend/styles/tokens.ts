// tokens.ts
// Role: Design system source of truth - defines CSS variables for colors, border radius, spacing,
// typography weights/sizes, and shadows used across all components via Tailwind

// UI-Pro Design Tokens
// Base design system - source of truth for all styling

import type { CSSProperties } from 'react'

/** 🎨 Colors */
export const colors = {
  bg: {
    primary: '#020617',      // deep dark
    secondary: '#0f172a',    // panels
    tertiary: '#020617cc',   // overlays
  },

  surface: {
    primary: '#0f172a',
    secondary: '#1e293b',
    hover: '#334155',
  },

  border: {
    subtle: '#1e293b',
    default: '#334155',
    strong: '#475569',
  },

  text: {
    primary: '#f8fafc',
    secondary: '#cbd5f5',
    muted: '#64748b',
    disabled: '#475569',
  },

  accent: {
    primary: '#7c3aed',   // violet
    hover: '#6d28d9',
    soft: '#a78bfa33',
  },

  success: '#22c55e',
  warning: '#eab308',
  error: '#ef4444',
}

/** 🧊 Radius */
export const radius = {
  sm: '6px',
  md: '10px',
  lg: '14px',
  xl: '18px',
  full: '999px',
}

/** 📏 Spacing */
export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
  xxl: '32px',
}

/** 🔤 Typography */
export const typography = {
  font: 'Inter, sans-serif',

  size: {
    xs: '12px',
    sm: '13px',
    md: '14px',
    lg: '16px',
    xl: '18px',
    xxl: '20px',
  },

  weight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  }
}

/** ✨ Shadows */
export const shadows = {
  sm: '0 1px 2px rgba(0,0,0,0.2)',
  md: '0 4px 12px rgba(0,0,0,0.4)',
  lg: '0 10px 30px rgba(0,0,0,0.6)',
}

/** 🔧 CSS Variables for dynamic theming */
export function generateCSSVariables(): CSSProperties {
  return {
    '--colors-bg-primary': colors.bg.primary,
    '--colors-bg-secondary': colors.bg.secondary,
    '--colors-bg-tertiary': colors.bg.tertiary,
    '--colors-surface-primary': colors.surface.primary,
    '--colors-surface-secondary': colors.surface.secondary,
    '--colors-surface-hover': colors.surface.hover,
    '--colors-border-subtle': colors.border.subtle,
    '--colors-border-default': colors.border.default,
    '--colors-border-strong': colors.border.strong,
    '--colors-text-primary': colors.text.primary,
    '--colors-text-secondary': colors.text.secondary,
    '--colors-text-muted': colors.text.muted,
    '--colors-text-disabled': colors.text.disabled,
    '--colors-accent-primary': colors.accent.primary,
    '--colors-accent-hover': colors.accent.hover,
    '--colors-accent-soft': colors.accent.soft,
    '--colors-success': colors.success,
    '--colors-warning': colors.warning,
    '--colors-error': colors.error,
    '--radius-sm': radius.sm,
    '--radius-md': radius.md,
    '--radius-lg': radius.lg,
    '--radius-xl': radius.xl,
    '--radius-full': radius.full,
    '--spacing-xs': spacing.xs,
    '--spacing-sm': spacing.sm,
    '--spacing-md': spacing.md,
    '--spacing-lg': spacing.lg,
    '--spacing-xl': spacing.xl,
    '--spacing-xxl': spacing.xxl,
    '--font-family': typography.font,
    '--shadow-sm': shadows.sm,
    '--shadow-md': shadows.md,
    '--shadow-lg': shadows.lg,
  }
}
