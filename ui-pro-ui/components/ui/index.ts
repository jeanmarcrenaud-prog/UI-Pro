// ui/index.ts
// Role: Barrel exports for UI components - exposes all design system components (Button, Card, Input, Textarea, Select, Badge)

// UI Component barrel exports
// All components use design system tokens

export { type ButtonComponentVariant as ButtonVariant } from './button'

export { Card } from './card'

export { InputComponent as Input, type InputComponentProps as InputProps } from './input'
export { TextareaComponent as Textarea, type TextareaComponentProps as TextareaProps } from './textarea'
export { SelectComponent as Select, type SelectComponentProps as SelectProps } from './select'
export { BadgeComponent as Badge, type BadgeVariant } from './badge'
