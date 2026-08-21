import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Play, Pause, Mic2, Gauge, Sparkles } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

const WORDS = 'The government has announced new financial support for eligible farmers this month'.split(' ')
const VOICES = ['Meera', 'Arjun', 'Ananya', 'Rahim']
const SPEEDS = ['0.85x', '1x', '1.15x', '1.3x']

export default function VoiceKaraoke() {
  const navigate = useNavigate()
  const [playing, setPlaying] = useState(false)
  const [wordIndex, setWordIndex] = useState(-1)
  const [voice, setVoice] = useState('Meera')
  const [speed, setSpeed] = useState('1x')
  const progressRef = useRef<HTMLDivElement>(null)
  const timers = useRef<number[]>([])

  const clearTimers = () => {
    timers.current.forEach((t) => clearTimeout(t))
    timers.current = []
  }

  const play = () => {
    setPlaying(true)
    setWordIndex(-1)
    clearTimers()
    const speedFactor = speed === '0.85x' ? 1.18 : speed === '1.15x' ? 0.87 : speed === '1.3x' ? 0.77 : 1
    let t = 0
    WORDS.forEach((w, i) => {
      const dur = (220 + w.length * 45) * speedFactor
      t += dur
      const id = window.setTimeout(() => setWordIndex(i), t)
      timers.current.push(id)
    })
    const endId = window.setTimeout(() => {
      setPlaying(false)
      setWordIndex(-1)
    }, t + 400)
    timers.current.push(endId)

    if (progressRef.current) {
      gsap.fromTo(progressRef.current, { width: '0%' }, { width: '100%', duration: t / 1000, ease: 'none' })
    }
  }

  const pause = () => {
    setPlaying(false)
    clearTimers()
    if (progressRef.current) gsap.killTweensOf(progressRef.current)
  }

  useEffect(() => () => clearTimers(), [])

  return (
    <PageShell showBack backTo="/admin/storyboard" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={5} />

        <div className="mt-8 flex items-center gap-2">
          <Mic2 size={22} className="text-blossom-500" />
          <h1 className="font-display text-3xl font-semibold text-plum-900">Voice and karaoke</h1>
        </div>
        <p className="mt-2 text-plum-800/70">Neural narration with word-level timing, generated for accessible captions.</p>

        <div className="mt-7 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card strong className="lg:col-span-2">
            <div className="flex items-center gap-4">
              <button
                onClick={() => (playing ? pause() : play())}
                className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-blossom-400 to-blossom-500 text-white shadow-glow hover:scale-105 transition-transform"
                aria-label={playing ? 'Pause narration' : 'Play narration'}
              >
                {playing ? <Pause size={22} /> : <Play size={22} className="ml-0.5" />}
              </button>
              <div className="flex-1">
                <p className="text-sm font-medium text-plum-900">{voice} &middot; {speed}</p>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blossom-50">
                  <div ref={progressRef} className="h-full w-0 rounded-full bg-linear-to-r from-blossom-400 to-skycandy-400" />
                </div>
              </div>
            </div>

            <div className="mt-8 rounded-2xl bg-white/60 p-6 leading-loose text-lg sm:text-xl font-display">
              {WORDS.map((w, i) => (
                <span
                  key={i}
                  className={`transition-colors duration-150 ${
                    i === wordIndex
                      ? 'text-blossom-600 font-semibold'
                      : i < wordIndex
                      ? 'text-plum-900/80'
                      : 'text-plum-800/35'
                  }`}
                >
                  {w}{' '}
                </span>
              ))}
            </div>
          </Card>

          <Card className="space-y-6 h-fit">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Mic2 size={15} className="text-blossom-500" />
                <h3 className="text-sm font-semibold text-plum-900">Narrator voice</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {VOICES.map((v) => (
                  <button
                    key={v}
                    onClick={() => setVoice(v)}
                    className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
                      voice === v ? 'bg-blossom-400 text-white' : 'bg-blossom-50 text-plum-800/70 hover:bg-blossom-100'
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-3">
                <Gauge size={15} className="text-skycandy-500" />
                <h3 className="text-sm font-semibold text-plum-900">Speaking speed</h3>
              </div>
              <div className="flex flex-wrap gap-2">
                {SPEEDS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSpeed(s)}
                    className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
                      speed === s ? 'bg-skycandy-400 text-plum-900' : 'bg-skycandy-50 text-plum-800/70 hover:bg-skycandy-100'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-2xl bg-blossom-50/70 p-4 flex items-start gap-2">
              <Sparkles size={15} className="text-blossom-500 mt-0.5 shrink-0" />
              <p className="text-xs text-plum-800/70 leading-relaxed">
                Captions export automatically as SRT and VTT once narration is approved.
              </p>
            </div>
          </Card>
        </div>

        <div className="mt-10 flex justify-end">
          <Button onClick={() => navigate('/admin/approval')}>Send for officer approval</Button>
        </div>
      </div>
    </PageShell>
  )
}
