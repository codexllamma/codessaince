import { type HTMLAttributes, type ReactNode } from 'react'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  strong?: boolean
}

export default function Card({ children, strong = false, className = '', ...props }: CardProps) {
  return (
    <div
      className={`${strong ? 'glass-strong' : 'glass'} rounded-3xl p-6 shadow-[0_10px_40px_-15px_rgba(74,44,61,0.25)] ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}
