import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Sprout, Landmark, Newspaper, Vote, Check } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp } from '../../Context/AppContext'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

const QUADRANTS = [
  {
    key: 'Agriculture',
    icon: Sprout,
    color: 'from-green-100 to-white',
    from: { x: '-120%', y: '-120%' },
    json: '{\n  "scheme": "PM Kisan",\n  "installment": "16th",\n  "amount": "₹2,000"\n}',
  },
  {
    key: 'Finance',
    icon: Landmark,
    color: 'from-skycandy-100 to-white',
    from: { x: '120%', y: '-120%' },
    json: '{\n  "sector": "banking",\n  "rate_change": "+0.25%",\n  "effective": "01 Sep"\n}',
  },
  {
    key: 'News',
    icon: Newspaper,
    color: 'from-peachcandy/60 to-white',
    from: { x: '-120%', y: '120%' },
    json: '{\n  "type": "advisory",\n  "region": "district",\n  "issued_by": "health dept"\n}',
  },
  {
    key: 'Politics',
    icon: Vote,
    color: 'from-lavendercandy/50 to-white',
    from: { x: '120%', y: '120%' },
    json: '{\n  "event": "election",\n  "phase": "nomination",\n  "deadline": "TBD"\n}',
  },
] as const

export default function SplitScreenCategorize() {
  const navigate = useNavigate()
  const { uploadedFileName } = useApp()
  const [primary, setPrimary] = useState<string>('Agriculture')
  const [animDone, setAnimDone] = useState(false)
  const stageRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ onComplete: () => setAnimDone(true) })
      tl.fromTo(
        '.center-doc',
        { scale: 1, opacity: 1 },
        { scale: 0.9, opacity: 0, duration: 0.6, ease: 'power1.in' }
      )
      tl.fromTo(
        '.quad-panel',
        {
          x: (i: number) => QUADRANTS[i].from.x,
          y: (i: number) => QUADRANTS[i].from.y,
          opacity: 0,
        },
        {
          x: '0%',
          y: '0%',
          opacity: 1,
          duration: 1.3,
          ease: 'power2.out',
          stagger: 0.12,
        },
        '-=0.2'
      )
      tl.fromTo(
        '.quad-json',
        { opacity: 0, y: 8 },
        { opacity: 1, y: 0, duration: 0.5, stagger: 0.08 },
        '-=0.5'
      )
    }, stageRef)
    return () => ctx.revert()
  }, [])

  return (
    <PageShell showBack backTo="/admin/upload" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={1} />

        <h1 className="mt-8 font-display text-3xl font-semibold text-plum-900">Splitting the notice by domain</h1>
        <p className="mt-2 text-plum-800/70">
          {uploadedFileName || 'The document'} is being classified into structured JSON across four outreach domains.
        </p>

        <div ref={stageRef} className="relative mt-10 min-h-105">
          <div className="center-doc absolute inset-0 flex items-center justify-center">
            <div className="glass-strong rounded-3xl px-8 py-10 text-center shadow-glow">
              <p className="font-display text-lg font-semibold text-plum-900">Extracted document JSON</p>
              <p className="text-sm text-plum-800/60 mt-1">Splitting into domain buckets…</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {QUADRANTS.map((q) => {
              const selected = primary === q.key
              return (
                <button
                  key={q.key}
                  onClick={() => setPrimary(q.key)}
                  className={`quad-panel text-left rounded-3xl p-5 bg-linear-to-br ${q.color} border transition-all ${
                    selected ? 'border-blossom-400 ring-2 ring-blossom-300 shadow-glow -translate-y-1' : 'border-white/70 hover:-translate-y-0.5'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/80 text-plum-800 shadow-sm">
                      <q.icon size={18} />
                    </span>
                    {selected && (
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blossom-500 text-white">
                        <Check size={13} />
                      </span>
                    )}
                  </div>
                  <p className="mt-3 font-display font-semibold text-plum-900">{q.key}</p>
                  <pre className="quad-json mt-2 rounded-xl bg-white/70 p-3 text-[11px] leading-relaxed text-plum-800/80 overflow-x-auto font-mono">
                    {q.json}
                  </pre>
                </button>
              )
            })}
          </div>
        </div>

        <div className="mt-10 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-sm text-plum-800/60">
            Primary domain: <span className="font-medium text-plum-900">{primary}</span>
          </p>
          <Button disabled={!animDone} onClick={() => navigate('/admin/ingest')}>
            Confirm and continue
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
