import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Check, Globe2, FileText } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp } from '../../Context/AppContext'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

const ALL_LANGUAGES = ['Hindi', 'Bengali', 'Tamil', 'Telugu', 'Marathi', 'Gujarati', 'Kannada', 'Malayalam', 'Punjabi', 'Odia', 'Assamese', 'English']

export default function NoticeIngest() {
  const navigate = useNavigate()
  const { uploadedFileName, targetLanguages, setTargetLanguages } = useApp()
  const gridRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.lang-tile', { y: 14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.35, stagger: 0.04, ease: 'power2.out' })
    }, gridRef)
    return () => ctx.revert()
  }, [])

  const toggle = (lang: string) => {
    setTargetLanguages(
      targetLanguages.includes(lang) ? targetLanguages.filter((l) => l !== lang) : [...targetLanguages, lang]
    )
  }

  return (
    <PageShell showBack backTo="/admin/categorize" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={2} />

        <h1 className="mt-8 font-display text-3xl font-semibold text-plum-900">Notice ingest</h1>
        <p className="mt-2 text-plum-800/70">Confirm the source and choose target languages for generation.</p>

        <Card className="mt-6 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blossom-100 text-blossom-500">
            <FileText size={18} />
          </span>
          <div>
            <p className="text-sm font-medium text-plum-900">{uploadedFileName || 'National-Circular-2026.pdf'}</p>
            <p className="text-xs text-plum-800/55">Source document &middot; ready to ingest</p>
          </div>
        </Card>

        <div className="mt-8">
          <div className="flex items-center gap-2 mb-3">
            <Globe2 size={18} className="text-skycandy-500" />
            <h2 className="font-display text-lg font-semibold text-plum-900">Target languages</h2>
            <span className="text-xs text-plum-800/50">(minimum three required)</span>
          </div>
          <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {ALL_LANGUAGES.map((lang) => {
              const active = targetLanguages.includes(lang)
              return (
                <button
                  key={lang}
                  onClick={() => toggle(lang)}
                  className={`lang-tile flex items-center justify-between rounded-2xl px-4 py-3 text-sm font-medium transition-all ${
                    active ? 'bg-linear-to-r from-blossom-400 to-blossom-500 text-white shadow-glow' : 'glass text-plum-800/75 hover:bg-blossom-50'
                  }`}
                >
                  {lang}
                  {active && <Check size={15} />}
                </button>
              )
            })}
          </div>
        </div>

        <div className="mt-10 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-sm text-plum-800/60">{targetLanguages.length} language{targetLanguages.length !== 1 ? 's' : ''} selected</p>
          <Button disabled={targetLanguages.length < 3} onClick={() => navigate('/admin/fact-grounding')}>
            Continue to fact grounding
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
