import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Play, Pause, Download, Share2, Captions, Sparkles } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import { useApp } from '../../Context/AppContext'

const CAPTION_LINES = [
  'The government has announced a new benefit for eligible citizens.',
  'Applications open from the first of next month at local centres.',
  'No processing fee is charged at any stage of this scheme.',
]

export default function Videos() {
  const navigate = useNavigate()
  const { selectedCircular, selectedLanguage, selectedAvatar } = useApp()
  const [playing, setPlaying] = useState(false)
  const [caption, setCaption] = useState(0)
  const [generating, setGenerating] = useState(true)
  const progressRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setGenerating(false), 1600)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => setCaption((c) => (c + 1) % CAPTION_LINES.length), 2600)
    const anim = gsap.to(progressRef.current, { width: '100%', duration: 8, ease: 'none' })
    return () => {
      clearInterval(id)
      anim.kill()
    }
  }, [playing])

  const avatarName = { meera: 'Meera', arjun: 'Arjun', ananya: 'Ananya', rahim: 'Rahim', priya: 'Priya', dev: 'Dev' }[
    selectedAvatar
  ] || 'your narrator'

  return (
    <PageShell showBack backTo="/user/avatar" wide density="medium">
      <div className="pt-4 sm:pt-8">
        <h1 className="font-display text-3xl font-semibold text-plum-900">Your video is ready</h1>
        <p className="mt-2 text-plum-800/70">
          {selectedCircular?.title || 'Government circular'} &middot; narrated in{' '}
          <span className="font-medium text-plum-900">{selectedLanguage || 'Hindi'}</span> by {avatarName}
        </p>

        <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card strong className="lg:col-span-2 p-0 overflow-hidden">
            <div className="relative aspect-video bg-gradient-to-br from-blossom-200 via-lavendercandy/60 to-skycandy-200 flex items-center justify-center">
              {generating ? (
                <div className="flex flex-col items-center text-plum-800">
                  <Sparkles className="animate-pulse" size={30} />
                  <span className="mt-3 text-sm font-medium">Rendering your video…</span>
                </div>
              ) : (
                <>
                  <button
                    onClick={() => setPlaying((p) => !p)}
                    className="flex h-16 w-16 items-center justify-center rounded-full bg-white/80 text-blossom-500 shadow-glow hover:scale-105 transition-transform"
                    aria-label={playing ? 'Pause video' : 'Play video'}
                  >
                    {playing ? <Pause size={26} /> : <Play size={26} className="ml-1" />}
                  </button>
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/50 to-transparent p-4">
                    <div className="flex items-center gap-2 text-xs text-white/90 mb-2">
                      <Captions size={14} />
                      <span className="line-clamp-1">{playing ? CAPTION_LINES[caption] : 'Captions ready in ' + (selectedLanguage || 'Hindi')}</span>
                    </div>
                    <div className="h-1 w-full overflow-hidden rounded-full bg-white/25">
                      <div ref={progressRef} className="h-full w-0 rounded-full bg-blossom-300" />
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="p-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-plum-900">{selectedCircular?.title}</p>
                <p className="text-xs text-plum-800/55 mt-0.5">{selectedCircular?.category} &middot; {selectedCircular?.date}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" icon={<Share2 size={15} />}>Share</Button>
                <Button size="sm" icon={<Download size={15} />}>Download</Button>
              </div>
            </div>
          </Card>

          <Card className="h-fit">
            <h3 className="font-display text-base font-semibold text-plum-900 mb-3">Summary</h3>
            <p className="text-sm text-plum-800/70 leading-relaxed">{selectedCircular?.summary}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {['Hindi', 'Tamil', 'Bengali', selectedLanguage].filter((v, i, a) => v && a.indexOf(v) === i).map((l) => (
                <span
                  key={l}
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    l === selectedLanguage ? 'bg-blossom-400 text-white' : 'bg-blossom-50 text-plum-800/70'
                  }`}
                >
                  {l}
                </span>
              ))}
            </div>
            <Button variant="ghost" size="sm" className="w-full mt-5" onClick={() => navigate('/user/circulars')}>
              Browse another circular
            </Button>
          </Card>
        </div>
      </div>
    </PageShell>
  )
}
