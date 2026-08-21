import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Check } from 'lucide-react'
import PageShell from '../../Components/PageShell'
//import Card from '../../components/ui/Card'
import Button from '../../Components/UI/Button'
import { useApp } from '../../Context/AppContext'

const LANGUAGES = [
  { name: 'Hindi', native: 'हिन्दी' },
  { name: 'Bengali', native: 'বাংলা' },
  { name: 'Tamil', native: 'தமிழ்' },
  { name: 'Telugu', native: 'తెలుగు' },
  { name: 'Marathi', native: 'मराठी' },
  { name: 'Gujarati', native: 'ગુજરાતી' },
  { name: 'Kannada', native: 'ಕನ್ನಡ' },
  { name: 'Malayalam', native: 'മലയാളം' },
  { name: 'Punjabi', native: 'ਪੰਜਾਬੀ' },
  { name: 'English', native: 'English' },
]

export default function LanguageSelect() {
  const navigate = useNavigate()
  const { selectedLanguage, setSelectedLanguage, selectedCircular } = useApp()
  const gridRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.lang-chip', { scale: 0.85, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.4, stagger: 0.04, ease: 'back.out(1.7)' })
    }, gridRef)
    return () => ctx.revert()
  }, [])

  return (
    <PageShell showBack backTo="/user/circulars">
      <div className="pt-4 sm:pt-10">
        <h1 className="font-display text-3xl font-semibold text-plum-900">Choose your language</h1>
        <p className="mt-2 text-plum-800/70">
          {selectedCircular ? (
            <>Narrating: <span className="font-medium text-plum-900">{selectedCircular.title}</span></>
          ) : (
            'Pick the language you would like this announcement narrated in.'
          )}
        </p>

        <div ref={gridRef} className="mt-8 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {LANGUAGES.map((l) => {
            const active = selectedLanguage === l.name
            return (
              <button
                key={l.name}
                onClick={() => setSelectedLanguage(l.name)}
                className={`lang-chip relative flex flex-col items-center justify-center gap-1 rounded-2xl py-6 px-3 transition-all ${
                  active
                    ? 'bg-gradient-to-br from-blossom-400 to-blossom-500 text-white shadow-glow scale-[1.03]'
                    : 'glass text-plum-800 hover:bg-blossom-50'
                }`}
              >
                {active && (
                  <span className="absolute top-2 right-2 flex h-5 w-5 items-center justify-center rounded-full bg-white/25">
                    <Check size={12} />
                  </span>
                )}
                <span className="font-display text-lg font-semibold">{l.native}</span>
                <span className={`text-xs ${active ? 'text-white/85' : 'text-plum-800/55'}`}>{l.name}</span>
              </button>
            )
          })}
        </div>

        <div className="mt-10 flex justify-end">
          <Button disabled={!selectedLanguage} onClick={() => navigate('/user/avatar')}>
            Continue
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
