import React from 'react'
import { Icon, type IconName } from './Icon'

export type ButtonVariant = 'primary' | 'secondary' | 'text' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: IconName
  iconPosition?: 'left' | 'right'
  loading?: boolean
  fullWidth?: boolean
  children: React.ReactNode
}

export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  iconPosition = 'left',
  loading = false,
  fullWidth = false,
  disabled,
  className = '',
  children,
  ...props
}: ButtonProps) {
  const isTextWithArrow =
    variant === 'text' &&
    !icon &&
    typeof children === 'string' &&
    !children.includes('→') &&
    !children.includes('↓') &&
    !children.includes('↑') &&
    !children.includes('←')

  return (
    <button
      className={`ui-btn ui-btn-${variant} ui-btn-${size} ${fullWidth ? 'ui-btn-full' : ''} ${loading ? 'ui-btn-loading' : ''} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <span className="ui-btn-spinner" />}
      {!loading && icon && iconPosition === 'left' && (
        <Icon name={icon} size={size === 'sm' ? 16 : 18} />
      )}
      <span className="ui-btn-label">{children}</span>
      {!loading && isTextWithArrow && (
        <span className="ui-btn-arrow" aria-hidden="true">→</span>
      )}
      {!loading && icon && iconPosition === 'right' && (
        <Icon name={icon} size={size === 'sm' ? 16 : 18} />
      )}
    </button>
  )
}
