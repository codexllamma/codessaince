import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Pencil, ShieldCheck, ShieldAlert, Tag, Loader2, AlertTriangle } from 'lucide-react'
import { toast } from 'react-toastify'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp } from '../../Context/AppContext'
import { api } from '../../api/client'
import type { ExtractedFact } from '../../api/client'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

/** Characters of surrounding notice text shown either side of the quoted span,
 *  so the officer can judge the fact in its sentence rather than alone. */
const CONTEXT_CHARS = 70

/** SCHEME_NAME -> "Scheme name". Derived rather than mapped, so a category the
 *  backend adds later still renders instead of falling through to blank. */
const categoryLabel = (category: string) => {
  const words = category.replace(/_/g, ' ').toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

const tidy = (s: string) => s.replace(/\s+/g, ' ')

interface Provenance {
  before: string
  quote: string
  after: string
}

export default function FactGrounding() {
  const navigate = useNavigate()
  const { job, jobId, rawText, setJob } = useApp()

  const [facts, setFacts] = useState<ExtractedFact[]>(job?.extracted_facts ?? [])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const rowsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setFacts(job?.extracted_facts ?? [])
  }, [job])

  // What the extractor originally proposed, so an edit that restores the
  // original value does not leave a phantom officer override behind.
  const originalValues = useMemo(
    () => new Map((job?.extracted_facts ?? []).map((f) => [f.fact_id, f.normalized_value])),
    [job]
  )

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.entity-row', { x: -16, opacity: 0 }, { x: 0, opacity: 1, duration: 0.4, stagger: 0.06, ease: 'power2.out' })
    }, rowsRef)
    return () => ctx.revert()
  }, [facts.length])

  const updateValue = (id: string, value: string) => {
    setFacts((prev) =>
      prev.map((f) =>
        f.fact_id === id
          ? {
              ...f,
              normalized_value: value,
              officer_override: value === originalValues.get(id) ? null : value,
            }
          : f
      )
    )
  }

  const toggleVerify = (id: string) => {
    setFacts((prev) => prev.map((f) => (f.fact_id === id ? { ...f, is_verified: !f.is_verified } : f)))
  }

  /** The passage the fact was grounded in, sliced out of the OCR text by the
   *  offsets the extractor recorded. Returns null when the offsets cannot be
   *  honoured — an unquoted fact is stated as such, never invented. */
  const provenanceFor = (fact: ExtractedFact): Provenance | null => {
    const { source_char_start: start, source_char_end: end } = fact
    if (!rawText || end <= start || start < 0 || start >= rawText.length) return null

    const stop = Math.min(end, rawText.length)
    const leadFrom = Math.max(0, start - CONTEXT_CHARS)
    const tailTo = Math.min(rawText.length, stop + CONTEXT_CHARS)

    return {
      before: (leadFrom > 0 ? '…' : '') + tidy(rawText.slice(leadFrom, start)),
      quote: tidy(rawText.slice(start, stop)),
      after: tidy(rawText.slice(stop, tailTo)) + (tailTo < rawText.length ? '…' : ''),
    }
  }

  const allVerified = facts.length > 0 && facts.every((f) => f.is_verified)

  const handleContinue = async () => {
    if (!jobId || saving) return
    setSaving(true)
    try {
      const updated = await api.updateFacts(jobId, facts)
      setJob(updated)
      const edited = facts.filter((f) => f.officer_override).length
      toast.success(
        edited > 0
          ? `Saved ${facts.length} facts to job ${jobId}, ${edited} with an officer override.`
          : `Saved ${facts.length} facts to job ${jobId}.`
      )
      navigate('/admin/storyboard')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      toast.error(message || 'Could not save the facts.')
    } finally {
      setSaving(false)
    }
  }

  if (!job || facts.length === 0) {
    return (
      <PageShell showBack backTo="/admin/ingest" wide>
        <div className="pt-4 sm:pt-8">
          <StepProgress steps={STEPS} current={3} />

          <h1 className="mt-8 font-display text-3xl font-semibold text-plum-900">Fact grounding</h1>
          <p className="mt-2 text-plum-800/70">
            Review each extracted entity against the source. Edit values or flag anything that can't be verified.
          </p>

          <Card className="mt-7 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-100 text-orange-500">
                <AlertTriangle size={18} />
              </span>
              <div>
                <p className="text-sm font-medium text-plum-900">
                  {job ? 'No facts were extracted from this notice' : 'No notice has been ingested yet'}
                </p>
                <p className="mt-1 text-xs text-plum-800/60">
                  {job
                    ? `Job ${job.job_id} was created from "${job.source_file_name}", but the extractor returned nothing to verify. Re-run the ingest, or check the PDF is machine-readable.`
                    : 'Facts appear here once the notice has been uploaded and read at the ingest step.'}
                </p>
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={() => navigate('/admin/ingest')}>
              Back to ingest
            </Button>
          </Card>
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell showBack backTo="/admin/ingest" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={3} />

        <h1 className="mt-8 font-display text-3xl font-semibold text-plum-900">Fact grounding</h1>
        <p className="mt-2 text-plum-800/70">
          Review each extracted entity against the source. Edit values or flag anything that can't be verified.
        </p>

        <div ref={rowsRef} className="mt-7 space-y-3">
          {facts.map((f) => {
            const provenance = provenanceFor(f)
            return (
              <Card key={f.fact_id} className="entity-row p-4 sm:p-5">
                <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                  <div className="flex items-center gap-2 sm:w-44 shrink-0">
                    <Tag size={14} className="text-blossom-500" />
                    <span className="text-xs font-medium uppercase tracking-wide text-plum-800/55">
                      {categoryLabel(f.category)}
                    </span>
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {editingId === f.fact_id ? (
                        <input
                          autoFocus
                          value={f.normalized_value}
                          onChange={(ev) => updateValue(f.fact_id, ev.target.value)}
                          onBlur={() => setEditingId(null)}
                          onKeyDown={(ev) => ev.key === 'Enter' && setEditingId(null)}
                          className="w-full rounded-xl border border-blossom-200 bg-white px-3 py-1.5 text-sm font-medium text-plum-900 outline-none focus:border-blossom-400"
                        />
                      ) : (
                        <button
                          onClick={() => setEditingId(f.fact_id)}
                          className="inline-flex items-center gap-2 text-sm font-medium text-plum-900 hover:text-blossom-600 transition-colors"
                        >
                          {f.normalized_value || <span className="text-plum-800/40">(empty)</span>}
                          <Pencil size={13} className="text-plum-800/40" />
                        </button>
                      )}
                      <span
                        className="rounded-full bg-skycandy-100 px-2.5 py-0.5 text-[11px] font-medium text-plum-800/70"
                        title="Extractor confidence for this fact"
                      >
                        {Math.round(f.confidence_score * 100)}% confidence
                      </span>
                      {f.officer_override && (
                        <span className="rounded-full bg-blossom-100 px-2.5 py-0.5 text-[11px] font-medium text-blossom-600">
                          Edited by officer
                        </span>
                      )}
                    </div>

                    {provenance ? (
                      <p className="mt-1 text-xs text-plum-800/50 italic leading-relaxed">
                        “{provenance.before}
                        <span className="not-italic font-medium text-plum-800/80">{provenance.quote}</span>
                        {provenance.after}”
                        {f.source_page ? (
                          <span className="not-italic text-plum-800/40"> &middot; page {f.source_page}</span>
                        ) : null}
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-orange-500/80 leading-relaxed">
                        Source passage unavailable — the recorded offsets do not resolve in the OCR text.
                      </p>
                    )}
                  </div>

                  <button
                    onClick={() => toggleVerify(f.fact_id)}
                    className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium shrink-0 transition-colors ${
                      f.is_verified ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-600'
                    }`}
                  >
                    {f.is_verified ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
                    {f.is_verified ? 'Verified' : 'Needs review'}
                  </button>
                </div>
              </Card>
            )
          })}
        </div>

        <div className="mt-10 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-sm text-plum-800/60">
            {facts.filter((f) => f.is_verified).length} of {facts.length} facts verified
          </p>
          <Button
            onClick={handleContinue}
            disabled={!allVerified || saving || !jobId}
            icon={saving ? <Loader2 size={17} className="animate-spin" /> : undefined}
            iconPosition="left"
            title={!allVerified ? 'Verify all facts to continue' : ''}
          >
            {saving ? 'Saving facts…' : 'Save and continue to storyboard'}
          </Button>
        </div>
        {!allVerified && <p className="mt-2 text-right text-xs text-orange-500">Mark all entities as verified to proceed.</p>}
      </div>
    </PageShell>
  )
}
