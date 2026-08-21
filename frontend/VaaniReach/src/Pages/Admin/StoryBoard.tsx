import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Clapperboard, ImageIcon } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp } from '../../Context/AppContext'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

const SCENES = [
  {
    id: 1,
    visual: 'from-blossom-200 to-peachcandy/70',
    text: {
      Hindi: 'सरकार ने पात्र किसानों के लिए एक नई सहायता राशि की घोषणा की है।',
      Tamil: 'தகுதியான விவசாயிகளுக்கு புதிய நிதி உதவியை அரசு அறிவித்துள்ளது.',
      Bengali: 'সরকার যোগ্য কৃষকদের জন্য একটি নতুন সহায়তা ঘোষণা করেছে।',
      English: 'The government has announced new financial support for eligible farmers.',
    },
  },
  {
    id: 2,
    visual: 'from-skycandy-200 to-lavendercandy/70',
    text: {
      Hindi: '16वीं किस्त के तहत ₹2,000 सीधे बैंक खातों में जमा किए गए हैं।',
      Tamil: '16வது தவணையின் கீழ் ₹2,000 நேரடியாக வங்கிக் கணக்குகளில் வரவு வைக்கப்பட்டுள்ளது.',
      Bengali: '১৬তম কিস্তির অধীনে ₹২,000 সরাসরি ব্যাংক অ্যাকাউন্টে জমা হয়েছে।',
      English: 'Under the 16th installment, ₹2,000 has been credited directly to bank accounts.',
    },
  },
  {
    id: 3,
    visual: 'from-peachcandy/70 to-blossom-200',
    text: {
      Hindi: 'पात्रता की जांच नजदीकी कृषि विज्ञान केंद्र पर की जा सकती है।',
      Tamil: 'தகுதியை அருகிலுள்ள வேளாண் அறிவியல் மையத்தில் சரிபார்க்கலாம்.',
      Bengali: 'নিকটবর্তী কৃষি বিজ্ঞান কেন্দ্রে যোগ্যতা যাচাই করা যাবে।',
      English: 'Eligibility can be verified at your nearest Krishi Vigyan Kendra.',
    },
  },
  {
    id: 4,
    visual: 'from-lavendercandy/70 to-skycandy-200',
    text: {
      Hindi: 'अधिक जानकारी के लिए आधिकारिक पोर्टल पर जाएं।',
      Tamil: 'மேலும் தகவலுக்கு அதிகாரப்பூர்வ போர்ட்டலைப் பார்வையிடவும்.',
      Bengali: 'আরও তথ্যের জন্য সরকারি পোর্টাল দেখুন।',
      English: 'Visit the official portal for more information.',
    },
  },
]

export default function StoryBoard() {
  const navigate = useNavigate()
  const { targetLanguages } = useApp()
  const languages = targetLanguages.length ? targetLanguages.slice(0, 4) : ['Hindi', 'Tamil', 'Bengali']
  const [activeLang, setActiveLang] = useState(languages[0] ?? 'Hindi')
  const selectedLang = languages.includes(activeLang) ? activeLang : languages[0] ?? 'Hindi'
  const gridRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.scene-card', { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.35, stagger: 0.07, ease: 'power2.out' })
    }, gridRef)
    return () => ctx.revert()
  }, [selectedLang])

  const textFor = (scene: (typeof SCENES)[number]) =>
    (scene.text as Record<string, string>)[selectedLang] || scene.text.English

  return (
    <PageShell showBack backTo="/admin/fact-grounding" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={4} />

        <div className="mt-8 flex items-center gap-2">
          <Clapperboard size={22} className="text-blossom-500" />
          <h1 className="font-display text-3xl font-semibold text-plum-900">Storyboard</h1>
        </div>
        <p className="mt-2 text-plum-800/70">Four scenes, generated per language. Switch languages to review each cut.</p>

        <div className="mt-6 flex flex-wrap gap-2">
          {languages.map((l) => (
            <button
              key={l}
              onClick={() => setActiveLang(l)}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                activeLang === l ? 'bg-linear-to-r from-blossom-400 to-blossom-500 text-white shadow-glow' : 'glass text-plum-800/70 hover:bg-blossom-50'
              }`}
            >
              {l}
            </button>
          ))}
        </div>

        <div ref={gridRef} className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-5">
          {SCENES.map((scene) => (
            <Card key={scene.id} className="scene-card p-0 overflow-hidden">
              <div className={`relative aspect-ratio:16/9 bg-linear-to-br ${scene.visual} flex items-center justify-center`}>
                <ImageIcon size={26} className="text-white/80" />
                <span className="absolute top-3 left-3 rounded-full bg-white/70 px-2.5 py-1 text-[11px] font-semibold text-plum-800">
                  Scene {scene.id}
                </span>
              </div>
              <div className="p-4">
                <p dir={activeLang === 'English' ? 'ltr' : 'auto'} className="text-sm leading-relaxed text-plum-900">
                  {textFor(scene)}
                </p>
              </div>
            </Card>
          ))}
        </div>

        <div className="mt-10 flex justify-end">
          <Button onClick={() => navigate('/admin/voice-karaoke')}>Continue to voice and karaoke</Button>
        </div>
      </div>
    </PageShell>
  )
}
