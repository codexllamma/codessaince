import { type ButtonHTMLAttributes, type ReactNode } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  icon?: ReactNode
  iconPosition?: 'left' | 'right'
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'right',
  className = '',
  ...props
}: ButtonProps) {
  const base =
    'inline-flex items-center justify-center gap-2 font-body font-medium rounded-full transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95'

  const variants: Record<string, string> = {
    primary:
      'bg-gradient-to-r from-blossom-700 to-blossom-800 text-plum-900 shadow-glow hover:shadow-xl hover:brightness-105',
    secondary:
      'bg-gradient-to-r from-skycandy-700 to-skycandy-800 text-plum-900 shadow-candy hover:brightness-105',
    outline:
      'border-2 border-blossom-700 text-blossom-800 bg-white/60 hover:bg-blossom-50',
    ghost: 'text-plum-800 hover:bg-blossom-100/70',
  }

  const sizes: Record<string, string> = {
    sm: 'px-4 py-2 text-sm',
    md: 'px-6 py-3 text-base',
    lg: 'px-8 py-4 text-lg',
  }

  return (
    <button className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...props}>
      {icon && iconPosition === 'left' && icon}
      {children}
      {icon && iconPosition === 'right' && icon}
    </button>
  )
}
