import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import gsap from 'gsap'
import { Check, Globe2, FileText, Loader2, AlertTriangle } from 'lucide-react'
import { toast } from 'react-toastify'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp, toLangCode } from '../../Context/AppContext'
import { api } from '../../api/client'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

const ALL_LANGUAGES = ['Hindi', 'Bengali', 'Tamil', 'Telugu', 'Marathi', 'Gujarati', 'Kannada', 'Malayalam', 'Punjabi', 'Odia', 'Assamese', 'English']

/** The job endpoint only accepts these codes (they are a Literal on the
 *  backend model), so anything else is rejected outright at job creation.
 *  The tiles stay selectable, but the officer is told which picks cannot be
 *  generated instead of losing a several-minute OCR run to a 422. */
const GENERATABLE_CODES = new Set(['en', 'hi', 'ta', 'te', 'bn', 'mr'])

/** OCR language for the source document. The flow has no screen on which the
 *  officer states what language the PDF itself is in, so this matches the
 *  backend's own default rather than guessing per document. */
const SOURCE_OCR_LANG = 'en'

type Stage = 'idle' | 'ocr' | 'job' | 'facts'

const STAGE_LABEL: Record<Exclude<Stage, 'idle'>, string> = {
  ocr: 'Uploading the PDF and reading it with OCR',
  job: 'Creating the job',
  facts: 'Storing the extracted facts',
}

export default function NoticeIngest() {
  const navigate = useNavigate()
  const {
    uploadedFile,
    uploadedFileName,
    targetLanguages,
    setTargetLanguages,
    setRawText,
    setJobId,
    setJob,
    selectedVoice,
  } = useApp()
  const gridRef = useRef<HTMLDivElement>(null)

  const [stage, setStage] = useState<Stage>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const busy = stage !== 'idle'

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.lang-tile', { y: 14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.35, stagger: 0.04, ease: 'power2.out' })
    }, gridRef)
    return () => ctx.revert()
  }, [])

  // OCR runs for minutes on CPU. A ticking counter is the difference between
  // "still working" and "this button is dead".
  useEffect(() => {
    if (!busy) return
    const id = window.setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => window.clearInterval(id)
  }, [busy])

  const toggle = (lang: string) => {
    if (busy) return
    setTargetLanguages(
      targetLanguages.includes(lang) ? targetLanguages.filter((l) => l !== lang) : [...targetLanguages, lang]
    )
  }

  const generatable = Array.from(new Set(targetLanguages.map(toLangCode).filter((c) => GENERATABLE_CODES.has(c))))
  const notGeneratable = targetLanguages.filter((l) => !GENERATABLE_CODES.has(toLangCode(l)))

  const handleIngest = async () => {
    if (!uploadedFile || busy) return

    setError(null)
    setElapsed(0)
    setStage('ocr')

    try {
      const doc = await api.uploadDocument(uploadedFile, SOURCE_OCR_LANG)
      const text = (doc.raw_text || '').trim()
      if (!text) {
        throw new Error(
          `OCR finished ${doc.pages_processed} page(s) of "${uploadedFileName}" but recovered no text. The PDF may be an unreadable scan.`
        )
      }
      setRawText(doc.raw_text)

      setStage('job')
      const created = await api.createJob(
        doc.raw_text,
        uploadedFileName || uploadedFile.name,
        generatable,
        selectedVoice || undefined
        // primary_lang is deliberately not sent: the backend treats it as an
        // instruction to OCR one of its own sample PDFs instead of this one.
      )

      // Job creation always returns an empty fact list; the facts belong to the
      // upload response, so they are written onto the job before step 4 reads it.
      let job = created
      const facts = doc.extracted_facts ?? doc.results ?? []
      if (facts.length > 0 && created.extracted_facts.length === 0) {
        setStage('facts')
        job = await api.updateFacts(created.job_id, facts)
      }

      setJobId(job.job_id)
      setJob(job)

      const factCount = job.extracted_facts.length
      toast.success(
        factCount > 0
          ? `Read ${doc.pages_processed} page(s) and extracted ${factCount} fact${factCount === 1 ? '' : 's'} (job ${job.job_id}).`
          : `Read ${doc.pages_processed} page(s) as job ${job.job_id}, but the extractor found no facts.`
      )
      navigate('/admin/fact-grounding')
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setError(message || 'Ingestion failed for an unknown reason.')
      toast.error(message || 'Ingestion failed for an unknown reason.')
    } finally {
      setStage('idle')
    }
  }

  // No minimum beyond "at least one" -- the backend's target_languages field
  // is a plain list (models/schemas.py) with no length constraint. The old
  // "at least three" rule was carried over uncritically from the scaffold's
  // original stock UI and never came from the API.
  const blocked = !uploadedFile || targetLanguages.length < 1 || generatable.length === 0

  return (
    <PageShell showBack backTo="/admin/categorize" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={2} />

        <h1 className="mt-8 font-display text-3xl font-semibold text-plum-900">Notice ingest</h1>
        <p className="mt-2 text-plum-800/70">Confirm the source and choose target languages for generation.</p>

        {uploadedFile ? (
          <Card className="mt-6 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blossom-100 text-blossom-500">
              <FileText size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-plum-900">{uploadedFileName || uploadedFile.name}</p>
              <p className="text-xs text-plum-800/55">Source document &middot; ready to ingest</p>
            </div>
          </Card>
        ) : (
          <Card className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-100 text-orange-500">
                <AlertTriangle size={18} />
              </span>
              <div>
                <p className="text-sm font-medium text-plum-900">No document is loaded</p>
                <p className="text-xs text-plum-800/55">
                  Nothing can be ingested until a PDF is chosen on the upload step.
                </p>
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={() => navigate('/admin/upload')}>
              Go to upload
            </Button>
          </Card>
        )}

        <div className="mt-8">
          <div className="flex items-center gap-2 mb-3">
            <Globe2 size={18} className="text-skycandy-500" />
            <h2 className="font-display text-lg font-semibold text-plum-900">Target languages</h2>
            <span className="text-xs text-plum-800/50">(at least one required)</span>
          </div>
          <div ref={gridRef} className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {ALL_LANGUAGES.map((lang) => {
              const active = targetLanguages.includes(lang)
              return (
                <button
                  key={lang}
                  onClick={() => toggle(lang)}
                  disabled={busy}
                  className={`lang-tile flex items-center justify-between rounded-2xl px-4 py-3 text-sm font-medium transition-all disabled:opacity-60 disabled:cursor-not-allowed ${
                    active ? 'bg-linear-to-r from-blossom-400 to-blossom-500 text-white shadow-glow' : 'glass text-plum-800/75 hover:bg-blossom-50'
                  }`}
                >
                  {lang}
                  {active && <Check size={15} />}
                </button>
              )
            })}
          </div>
          {notGeneratable.length > 0 && (
            <p className="mt-3 text-xs text-orange-500">
              {notGeneratable.join(', ')} {notGeneratable.length === 1 ? 'is' : 'are'} not available in the generator yet —
              {generatable.length > 0
                ? ` the job will be created for ${generatable.join(', ')} only.`
                : ' pick at least one of English, Hindi, Tamil, Telugu, Bengali or Marathi.'}
            </p>
          )}
        </div>

        {busy && (
          <Card className="mt-6 flex items-start gap-3">
            <Loader2 size={18} className="mt-0.5 shrink-0 animate-spin text-blossom-500" />
            <div>
              <p className="text-sm font-medium text-plum-900">
                {STAGE_LABEL[stage as Exclude<Stage, 'idle'>]}… {Math.floor(elapsed / 60)}m {elapsed % 60}s elapsed
              </p>
              <p className="mt-1 text-xs text-plum-800/55">
                OCR runs on the server and can take several minutes for a scanned notice. Keep this tab open.
              </p>
            </div>
          </Card>
        )}

        {error && !busy && (
          <Card className="mt-6 flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-orange-500" />
            <div>
              <p className="text-sm font-medium text-plum-900">Ingestion failed — nothing was created</p>
              <p className="mt-1 text-xs text-plum-800/60 wrap-break-word whitespace-pre-wrap">{error}</p>
            </div>
          </Card>
        )}

        <div className="mt-10 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-sm text-plum-800/60">{targetLanguages.length} language{targetLanguages.length !== 1 ? 's' : ''} selected</p>
          <Button
            disabled={blocked || busy}
            onClick={handleIngest}
            icon={busy ? <Loader2 size={17} className="animate-spin" /> : undefined}
            iconPosition="left"
            title={!uploadedFile ? 'Choose a PDF on the upload step first' : ''}
          >
            {busy ? 'Ingesting…' : error ? 'Retry ingest' : 'Ingest and continue'}
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
