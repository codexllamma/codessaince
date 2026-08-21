import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Check, AlertCircle, Loader2 } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Button from '../../Components/UI/Button'
import { useApp } from '../../Context/AppContext'
import { api, type AvatarInfo } from '../../api/client'

// Presenter cards have no portrait to show, so each gets a colour from this
// list by position. Picking by index rather than at random keeps a given
// presenter the same colour between visits.
const GRADIENTS = [
  'from-blossom-300 to-peachcandy',
  'from-skycandy-300 to-skycandy-400',
  'from-lavendercandy to-blossom-200',
  'from-skycandy-200 to-lavendercandy',
  'from-peachcandy to-blossom-200',
  'from-blossom-200 to-skycandy-200',
]

export default function AvatarSelect() {
  const navigate = useNavigate()
  const { selectedAvatar, setSelectedAvatar } = useApp()
  const gridRef = useRef<HTMLDivElement>(null)

  const [avatars, setAvatars] = useState<AvatarInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .listAvatars()
      .then((list) => {
        if (cancelled) return
        setAvatars(list)
        setError(null)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Could not reach the server')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (loading || avatars.length === 0) return
    const ctx = gsap.context(() => {
      gsap.fromTo(
        '.avatar-card',
        { y: 24, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.45, stagger: 0.07, ease: 'power2.out' }
      )
    }, gridRef)
    return () => ctx.revert()
  }, [loading, avatars])

  return (
    <PageShell showBack backTo="/user/language">
      <div className="pt-4 sm:pt-10">
        <h1 className="font-display text-3xl font-semibold text-plum-900">Pick your narrator</h1>
        <p className="mt-2 text-plum-800/70">
          Every narrator here is computer-generated. None of them is a government official.
        </p>

        {loading && (
          <div className="mt-10 flex items-center gap-3 text-plum-800/70">
            <Loader2 size={18} className="animate-spin" />
            <span>Loading narrators…</span>
          </div>
        )}

        {!loading && error && (
          <div className="mt-8 flex items-start gap-3 rounded-2xl bg-white/70 p-5 text-plum-900">
            <AlertCircle size={18} className="mt-0.5 shrink-0 text-blossom-600" />
            <div>
              <p className="font-medium">Could not load narrators</p>
              <p className="mt-1 text-sm text-plum-800/70 wrap-break-word">{error}</p>
              <p className="mt-2 text-sm text-plum-800/60">
                Check that the backend is running at the configured address, then reload.
              </p>
            </div>
          </div>
        )}

        {/* An empty list is a legitimate backend state -- it means no presenter
            is installed, and the compositor renders its full-width layout
            instead. Say that rather than showing an empty grid. */}
        {!loading && !error && avatars.length === 0 && (
          <div className="mt-8 rounded-2xl bg-white/70 p-5 text-plum-900">
            <p className="font-medium">No narrators are installed</p>
            <p className="mt-1 text-sm text-plum-800/70">
              Videos will still be produced, but without an on-screen presenter.
            </p>
            <div className="mt-5">
              <Button onClick={() => navigate('/user/videos')}>Continue anyway</Button>
            </div>
          </div>
        )}

        {!loading && !error && avatars.length > 0 && (
          <>
            <div ref={gridRef} className="mt-8 grid grid-cols-2 sm:grid-cols-3 gap-4 sm:gap-5">
              {avatars.map((a, i) => {
                const active = selectedAvatar === a.avatar_id
                return (
                  <button
                    key={a.avatar_id}
                    onClick={() => setSelectedAvatar(a.avatar_id)}
                    className={`avatar-card group relative flex flex-col items-center rounded-3xl p-5 text-center transition-all ${
                      active ? 'glass-strong ring-2 ring-blossom-400 shadow-glow -translate-y-1' : 'glass hover:-translate-y-1'
                    }`}
                  >
                    {active && (
                      <span className="absolute top-3 right-3 flex h-6 w-6 items-center justify-center rounded-full bg-blossom-500 text-white">
                        <Check size={13} />
                      </span>
                    )}
                    <span
                      className={`relative flex h-20 w-20 items-center justify-center rounded-full bg-linear-to-br ${
                        GRADIENTS[i % GRADIENTS.length]
                      } text-white shadow-md mb-3`}
                    >
                      <span className="font-display text-2xl font-semibold">
                        {(a.display_name || a.avatar_id).charAt(0).toUpperCase()}
                      </span>
                    </span>
                    <span className="font-display text-base font-semibold text-plum-900">
                      {a.display_name || a.avatar_id}
                    </span>
                    <span className="text-xs text-plum-800/60 mt-0.5">
                      {a.languages.includes('*') ? 'All languages' : a.languages.join(', ').toUpperCase()}
                    </span>

                    {/* Shown on every card, not only the selected one, and never
                        truncated. A viewer has to be able to tell what they are
                        looking at before they pick it. */}
                    {a.disclosure_label && (
                      <span className="mt-3 rounded-full bg-plum-900/85 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
                        {a.disclosure_label}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>

            <div className="mt-10 flex justify-end">
              <Button disabled={!selectedAvatar} onClick={() => navigate('/user/videos')}>
                Generate my video
              </Button>
            </div>
          </>
        )}
      </div>
    </PageShell>
  )
}
