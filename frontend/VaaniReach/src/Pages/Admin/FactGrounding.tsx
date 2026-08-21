import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Pencil, ShieldCheck, ShieldAlert, Tag } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

interface Entity {
  id: string
  type: string
  value: string
  source: string
  verified: boolean
}

const INITIAL: Entity[] = [
  { id: 'e1', type: 'Scheme name', value: 'PM Kisan Samman Nidhi', source: '"...under the PM Kisan Samman Nidhi scheme..."', verified: true },
  { id: 'e2', type: 'Amount', value: '₹2,000', source: '"...a sum of ₹2,000 has been credited..."', verified: true },
  { id: 'e3', type: 'Installment', value: '16th', source: '"...as part of the 16th installment..."', verified: true },
  { id: 'e4', type: 'Date', value: '18 August 2026', source: '"...disbursed on 18 August 2026..."', verified: false },
  { id: 'e5', type: 'Issuing authority', value: 'Ministry of Agriculture', source: '"...notified by the Ministry of Agriculture..."', verified: true },
  { id: 'e6', type: 'Eligibility', value: 'Registered smallholder farmers', source: '"...applicable to registered smallholder farmers..."', verified: false },
]

export default function FactGrounding() {
  const navigate = useNavigate()
  const [entities, setEntities] = useState(INITIAL)
  const [editingId, setEditingId] = useState<string | null>(null)
  const rowsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.entity-row', { x: -16, opacity: 0 }, { x: 0, opacity: 1, duration: 0.4, stagger: 0.06, ease: 'power2.out' })
    }, rowsRef)
    return () => ctx.revert()
  }, [])

  const updateValue = (id: string, value: string) => {
    setEntities((prev) => prev.map((e) => (e.id === id ? { ...e, value } : e)))
  }

  const toggleVerify = (id: string) => {
    setEntities((prev) => prev.map((e) => (e.id === id ? { ...e, verified: !e.verified } : e)))
  }

  const allVerified = entities.every((e) => e.verified)

  return (
    <PageShell showBack backTo="/admin/ingest" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={3} />

        <h1 className="mt-8 font-display text-3xl font-semibold text-plum-900">Fact grounding</h1>
        <p className="mt-2 text-plum-800/70">
          Review each extracted entity against the source. Edit values or flag anything that can't be verified.
        </p>

        <div ref={rowsRef} className="mt-7 space-y-3">
          {entities.map((e) => (
            <Card key={e.id} className="entity-row p-4 sm:p-5">
              <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                <div className="flex items-center gap-2 sm:w-44 shrink-0">
                  <Tag size={14} className="text-blossom-500" />
                  <span className="text-xs font-medium uppercase tracking-wide text-plum-800/55">{e.type}</span>
                </div>

                <div className="flex-1">
                  {editingId === e.id ? (
                    <input
                      autoFocus
                      value={e.value}
                      onChange={(ev) => updateValue(e.id, ev.target.value)}
                      onBlur={() => setEditingId(null)}
                      onKeyDown={(ev) => ev.key === 'Enter' && setEditingId(null)}
                      className="w-full rounded-xl border border-blossom-200 bg-white px-3 py-1.5 text-sm font-medium text-plum-900 outline-none focus:border-blossom-400"
                    />
                  ) : (
                    <button
                      onClick={() => setEditingId(e.id)}
                      className="inline-flex items-center gap-2 text-sm font-medium text-plum-900 hover:text-blossom-600 transition-colors"
                    >
                      {e.value}
                      <Pencil size={13} className="text-plum-800/40" />
                    </button>
                  )}
                  <p className="mt-1 text-xs text-plum-800/50 italic leading-relaxed">{e.source}</p>
                </div>

                <button
                  onClick={() => toggleVerify(e.id)}
                  className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium shrink-0 transition-colors ${
                    e.verified ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-600'
                  }`}
                >
                  {e.verified ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
                  {e.verified ? 'Verified' : 'Needs review'}
                </button>
              </div>
            </Card>
          ))}
        </div>

        <div className="mt-10 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-sm text-plum-800/60">
            {entities.filter((e) => e.verified).length} of {entities.length} facts verified
          </p>
          <Button onClick={() => navigate('/admin/storyboard')} disabled={!allVerified} title={!allVerified ? 'Verify all facts to continue' : ''}>
            Continue to storyboard
          </Button>
        </div>
        {!allVerified && <p className="mt-2 text-right text-xs text-orange-500">Mark all entities as verified to proceed.</p>}
      </div>
    </PageShell>
  )
}
