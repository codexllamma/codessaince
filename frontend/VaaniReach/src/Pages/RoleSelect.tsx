import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { User, ShieldCheck, ArrowRight } from 'lucide-react'
import PageShell from '../Components/PageShell'
import Card from '../Components/UI/Card'
import { useApp } from '../Context/AppContext'

export default function RoleSelect() {
  const navigate = useNavigate()
  const { setRole } = useApp()
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.role-card', { y: 28, opacity: 0 }, { y: 0, opacity: 1, duration: 0.6, stagger: 0.15, ease: 'power3.out' })
    }, wrapRef)
    return () => ctx.revert()
  }, [])

  const choose = (role: 'user' | 'admin') => {
    setRole(role)
    navigate(role === 'user' ? '/user/login' : '/admin/upload')
  }

  return (
    <PageShell showBack backTo="/landing">
      <div ref={wrapRef} className="pt-6 sm:pt-14 text-center">
        <h1 className="font-display text-3xl sm:text-4xl font-semibold text-plum-900">How would you like to enter?</h1>
        <p className="mt-3 text-plum-800/70">Choose the experience that matches what you're here to do.</p>

        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-6">
          <Card
            strong
            className="role-card cursor-pointer group hover:-translate-y-1.5 transition-transform text-left"
            onClick={() => choose('user')}
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blossom-100 text-blossom-500 mb-4">
              <User size={22} />
            </span>
            <h2 className="font-display text-xl font-semibold text-plum-900">I'm a citizen</h2>
            <p className="mt-2 text-sm text-plum-800/70 leading-relaxed">
              Browse published circulars, pick your language and avatar, and watch the announcement that matters to you.
            </p>
            <span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-blossom-600 group-hover:gap-2 transition-all">
              Continue as citizen <ArrowRight size={16} />
            </span>
          </Card>

          <Card
            strong
            className="role-card cursor-pointer group hover:-translate-y-1.5 transition-transform text-left"
            onClick={() => choose('admin')}
          >
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-skycandy-100 text-skycandy-500 mb-4">
              <ShieldCheck size={22} />
            </span>
            <h2 className="font-display text-xl font-semibold text-plum-900">I'm an officer</h2>
            <p className="mt-2 text-sm text-plum-800/70 leading-relaxed">
              Upload a notice, verify extracted facts, build the multilingual storyboard, and approve the final video.
            </p>
            <span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-skycandy-500 group-hover:gap-2 transition-all">
              Continue as officer <ArrowRight size={16} />
            </span>
          </Card>
        </div>
      </div>
    </PageShell>
  )
}
