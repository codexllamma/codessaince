import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Sprout, Landmark, Newspaper, Vote, CalendarDays, ArrowRight } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import { useApp, type Circular } from '../../Context/AppContext'

const CATEGORIES = [
  { key: 'Agriculture', icon: Sprout, color: 'from-green-100 to-blossom-50 text-green-600' },
  { key: 'Finance', icon: Landmark, color: 'from-skycandy-100 to-blossom-50 text-skycandy-500' },
  { key: 'News', icon: Newspaper, color: 'from-peachcandy/60 to-blossom-50 text-orange-500' },
  { key: 'Politics', icon: Vote, color: 'from-lavendercandy/60 to-blossom-50 text-purple-500' },
] as const

const CIRCULARS: Circular[] = [
  {
    id: 'c1',
    title: 'PM Kisan Samman Nidhi — 16th installment released',
    category: 'Agriculture',
    date: '18 Aug 2026',
    summary: 'Direct benefit transfer of Rs 2,000 credited to eligible farmer accounts nationwide.',
  },
  {
    id: 'c2',
    title: 'Soil Health Card renewal window opens',
    category: 'Agriculture',
    date: '15 Aug 2026',
    summary: 'Farmers can renew soil health cards at nearest Krishi Vigyan Kendra until 30 Sept.',
  },
  {
    id: 'c3',
    title: 'Revised savings account interest rates',
    category: 'Finance',
    date: '20 Aug 2026',
    summary: 'Public sector banks announce updated interest rates effective 1 September.',
  },
  {
    id: 'c4',
    title: 'MSME collateral-free loan scheme extended',
    category: 'Finance',
    date: '12 Aug 2026',
    summary: 'Loans up to Rs 10 lakh now available without collateral for registered MSMEs.',
  },
  {
    id: 'c5',
    title: 'Monsoon session public health advisory',
    category: 'News',
    date: '19 Aug 2026',
    summary: 'District health departments issue guidance on waterborne disease prevention.',
  },
  {
    id: 'c6',
    title: 'New railway line inaugurated in the region',
    category: 'News',
    date: '14 Aug 2026',
    summary: 'The new line is expected to cut travel time between two major districts by half.',
  },
  {
    id: 'c7',
    title: 'Voter list revision drive begins',
    category: 'Politics',
    date: '17 Aug 2026',
    summary: 'Citizens can verify and update their entries at designated centres before the deadline.',
  },
  {
    id: 'c8',
    title: 'Panchayat election schedule announced',
    category: 'Politics',
    date: '10 Aug 2026',
    summary: 'Nomination filing begins next week across all participating districts.',
  },
]

export default function CircularSelect() {
  const navigate = useNavigate()
  const { setSelectedCircular, userName } = useApp()
  const [active, setActive] = useState<Circular['category'] | 'All'>('All')
  const gridRef = useRef<HTMLDivElement>(null)

  const filtered = active === 'All' ? CIRCULARS : CIRCULARS.filter((c) => c.category === active)

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        '.circular-card',
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.45, stagger: 0.06, ease: 'power2.out' }
      )
    }, gridRef)
    return () => ctx.revert()
  }, [active])

  const choose = (c: Circular) => {
    setSelectedCircular(c)
    navigate('/user/language')
  }

  return (
    <PageShell showBack backTo="/role" wide>
      <div className="pt-4 sm:pt-8">
        <h1 className="font-display text-3xl font-semibold text-plum-900">
          Hi{userName ? `, ${userName}` : ''}. What would you like to watch?
        </h1>
        <p className="mt-2 text-plum-800/70">Pick a circular — we'll narrate it in your language.</p>

        <div className="mt-6 flex flex-wrap gap-2">
          {(['All', ...CATEGORIES.map((c) => c.key)] as const).map((cat) => (
            <button
              key={cat}
              onClick={() => setActive(cat as never)}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                active === cat
                  ? 'bg-gradient-to-r from-blossom-400 to-blossom-500 text-white shadow-glow'
                  : 'glass text-plum-800/70 hover:bg-blossom-50'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        <div ref={gridRef} className="mt-7 grid grid-cols-1 sm:grid-cols-2 gap-5">
          {filtered.map((c) => {
            const meta = CATEGORIES.find((cat) => cat.key === c.category)!
            return (
              <Card
                key={c.id}
                className="circular-card cursor-pointer group hover:-translate-y-1 transition-transform text-left"
                onClick={() => choose(c)}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${meta.color}`}>
                    <meta.icon size={18} />
                  </span>
                  <span className="flex items-center gap-1 text-xs text-plum-800/50">
                    <CalendarDays size={13} /> {c.date}
                  </span>
                </div>
                <h3 className="mt-3 font-display text-base font-semibold text-plum-900 leading-snug">{c.title}</h3>
                <p className="mt-1.5 text-sm text-plum-800/65 leading-relaxed">{c.summary}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-blossom-600 group-hover:gap-2 transition-all">
                  Choose this circular <ArrowRight size={15} />
                </span>
              </Card>
            )
          })}
        </div>
      </div>
    </PageShell>
  )
}
