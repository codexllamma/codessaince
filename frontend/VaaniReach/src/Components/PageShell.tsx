import { type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, LogOut } from 'lucide-react'
import Logo from './Logo'
import PetalBackground from './PetalBackground'
import { useApp } from '../Context/AppContext'

interface PageShellProps {
  children: ReactNode
  showBack?: boolean
  backTo?: string
  density?: 'low' | 'medium' | 'high'
  wide?: boolean
}

export default function PageShell({ children, showBack = false, backTo, density = 'low', wide = false }: PageShellProps) {
  const navigate = useNavigate()
  const { role, setRole } = useApp()

  return (
    <div className="relative min-h-screen w-full bg-candy-sky-soft">
      <PetalBackground density={density} />
      <header className="relative z-10 flex items-center justify-between px-5 sm:px-8 py-5">
        <div className="flex items-center gap-3">
          {showBack && (
            <button
              onClick={() => (backTo ? navigate(backTo) : navigate(-1))}
              className="flex h-9 w-9 items-center justify-center rounded-full glass text-plum-800 hover:bg-blossom-100 transition-colors"
              aria-label="Go back"
            >
              <ArrowLeft size={18} />
            </button>
          )}
          <Logo />
        </div>
        {role && (
          <button
            onClick={() => {
              setRole(null)
              navigate('/role')
            }}
            className="flex items-center gap-1.5 rounded-full glass px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium text-plum-800 hover:bg-blossom-100 transition-colors"
          >
            <LogOut size={14} />
            <span className="hidden sm:inline">Switch role</span>
          </button>
        )}
      </header>
      <main className={`relative z-10 mx-auto px-5 sm:px-8 pb-16 ${wide ? 'max-w-6xl' : 'max-w-4xl'}`}>{children}</main>
    </div>
  )
}
