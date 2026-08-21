import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { ArrowRight, Languages, FileSearch, Wand2, ShieldCheck, Mic2, ClipboardCheck } from 'lucide-react'
import PetalBackground from '../Components/PetalBackground'
import Logo from '../Components/Logo'
import Button from '../Components/UI/Button'
import Card from '../Components/UI/Button'

const FEATURES = [
  {
    icon: FileSearch,
    title: 'Source understanding',
    desc: 'Extracts names, numbers, dates, locations and scheme details straight from the notice.',
  },
  {
    icon: Languages,
    title: 'Multilingual by default',
    desc: 'Every announcement is scripted and narrated in three or more Indian languages.',
  },
  {
    icon: Wand2,
    title: 'Multimodal video',
    desc: 'Narration, visuals and captions come together into one short, shareable video.',
  },
  {
    icon: ShieldCheck,
    title: 'Fact verification',
    desc: 'Generated facts are checked against the source before anything is published.',
  },
  {
    icon: Mic2,
    title: 'Neural voice + karaoke',
    desc: 'Natural narration with word-level timing for accessible, readable captions.',
  },
  {
    icon: ClipboardCheck,
    title: 'Officer review',
    desc: 'A human always signs off on the final video before it reaches the public.',
  },
]

export default function Landing() {
  const navigate = useNavigate()
  const heroRef = useRef<HTMLDivElement>(null)
  const featuresRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo(
        '.hero-item',
        { y: 24, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.7, stagger: 0.12, ease: 'power3.out' }
      )
      gsap.fromTo(
        '.feature-card',
        { y: 30, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.6,
          stagger: 0.08,
          ease: 'power2.out',
          delay: 0.4,
        }
      )
    })
    return () => ctx.revert()
  }, [])

  return (
    <div className="relative min-h-screen overflow-hidden bg-candy-sky-soft">
      <PetalBackground density="medium" />
      <header className="relative z-10 flex items-center justify-between px-5 sm:px-8 py-6">
        <Logo to="/landing" />
        <Button size="sm" variant="outline" onClick={() => navigate('/role')}>
          Enter studio
        </Button>
      </header>

      <section ref={heroRef} className="relative z-10 mx-auto max-w-5xl px-5 sm:px-8 pt-8 sm:pt-14 text-center">
        <span className="hero-item inline-block rounded-full glass px-4 py-1.5 text-xs sm:text-sm font-medium text-blossom-600 mb-6">
          PS-02 &middot; Multilingual Outreach Video Generator
        </span>
        <h1 className="hero-item font-display text-4xl sm:text-6xl font-semibold leading-tight text-plum-900">
          Every announcement,
          <br />
          <span className="text-gradient">in every language</span> it should speak
        </h1>
        <p className="hero-item mt-6 max-w-2xl mx-auto text-base sm:text-lg text-plum-800/75">
          Government notices reach only a fraction of their audience when they stay text-heavy and English-only.
          VaaniReach turns a press release into a narrated, captioned, fact-checked video — in minutes, not weeks.
        </p>
        <div className="hero-item mt-9 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button size="lg" icon={<ArrowRight size={18} />} onClick={() => navigate('/role')}>
            Get started
          </Button>
          <Button size="lg" variant="ghost" onClick={() => navigate('/role')}>
            See how it works
          </Button>
        </div>
      </section>

      <section ref={featuresRef} className="relative z-10 mx-auto max-w-6xl px-5 sm:px-8 py-16 sm:py-24">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6">
          {FEATURES.map((f) => (
            <Card key={f.title} className="feature-card">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-linear-to-br from-blossom-100 to-skycandy-100 text-blossom-500 mb-4">
                <f.icon size={20} />
              </span>
              <h3 className="font-display text-lg font-semibold text-plum-900">{f.title}</h3>
              <p className="mt-1.5 text-sm text-plum-800/70 leading-relaxed">{f.desc}</p>
            </Card>
          ))}
        </div>
      </section>

      <footer className="relative z-10 pb-10 text-center text-xs text-plum-800/50">
        VaaniReach &middot; Built for reach, not just for record
      </footer>
    </div>
  )
}
