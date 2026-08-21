import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Check, PlayCircle } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Button from '../../Components/UI/Button'
import { useApp } from '../../Context/AppContext'

const AVATARS = [
  { id: 'meera', name: 'Meera', role: 'Warm & friendly', gradient: 'from-blossom-300 to-peachcandy' },
  { id: 'arjun', name: 'Arjun', role: 'Formal & clear', gradient: 'from-skycandy-300 to-skycandy-400' },
  { id: 'ananya', name: 'Ananya', role: 'Youthful & energetic', gradient: 'from-lavendercandy to-blossom-200' },
  { id: 'rahim', name: 'Rahim', role: 'Calm & authoritative', gradient: 'from-skycandy-200 to-lavendercandy' },
  { id: 'priya', name: 'Priya', role: 'Reassuring & simple', gradient: 'from-peachcandy to-blossom-200' },
  { id: 'dev', name: 'Dev', role: 'Confident & brisk', gradient: 'from-blossom-200 to-skycandy-200' },
]

export default function AvatarSelect() {
  const navigate = useNavigate()
  const { selectedAvatar, setSelectedAvatar } = useApp()
  const gridRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.avatar-card', { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, stagger: 0.07, ease: 'power2.out' })
    }, gridRef)
    return () => ctx.revert()
  }, [])

  return (
    <PageShell showBack backTo="/user/language">
      <div className="pt-4 sm:pt-10">
        <h1 className="font-display text-3xl font-semibold text-plum-900">Pick your narrator</h1>
        <p className="mt-2 text-plum-800/70">Each avatar narrates with a distinct tone and pace.</p>

        <div ref={gridRef} className="mt-8 grid grid-cols-2 sm:grid-cols-3 gap-4 sm:gap-5">
          {AVATARS.map((a) => {
            const active = selectedAvatar === a.id
            return (
              <button
                key={a.id}
                onClick={() => setSelectedAvatar(a.id)}
                className={`avatar-card group relative flex flex-col items-center rounded-3xl p-5 transition-all ${
                  active ? 'glass-strong ring-2 ring-blossom-400 shadow-glow -translate-y-1' : 'glass hover:-translate-y-1'
                }`}
              >
                {active && (
                  <span className="absolute top-3 right-3 flex h-6 w-6 items-center justify-center rounded-full bg-blossom-500 text-white">
                    <Check size={13} />
                  </span>
                )}
                <span
                  className={`relative flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br ${a.gradient} text-white shadow-md mb-3`}
                >
                  <span className="font-display text-2xl font-semibold">{a.name[0]}</span>
                  <span className="absolute -bottom-1 -right-1 flex h-7 w-7 items-center justify-center rounded-full bg-white text-blossom-500 shadow-sm opacity-0 group-hover:opacity-100 transition-opacity">
                    <PlayCircle size={16} />
                  </span>
                </span>
                <span className="font-display text-base font-semibold text-plum-900">{a.name}</span>
                <span className="text-xs text-plum-800/60 mt-0.5">{a.role}</span>
              </button>
            )
          })}
        </div>

        <div className="mt-10 flex justify-end">
          <Button disabled={!selectedAvatar} onClick={() => navigate('/user/videos')}>
            Generate my video
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
