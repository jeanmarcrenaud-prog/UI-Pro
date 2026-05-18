// ui/index.ts
// Role: Barrel exports for UI components - exposes all design system components (Button, Card, Input, Textarea, Select, Badge)

// UI Component barrel exports
// All components use design system tokens

export { type ButtonComponentVariant as ButtonVariant } from './button'

export { Card } from './Card'

export { InputComponent as Input, type InputComponentProps as InputProps } from './Input'
export { TextareaComponent as Textarea, type TextareaComponentProps as TextareaProps } from './Textarea'
export { SelectComponent as Select, type SelectComponentProps as SelectProps } from './Select'
export { BadgeComponent as Badge, type BadgeVariant } from './badge'
