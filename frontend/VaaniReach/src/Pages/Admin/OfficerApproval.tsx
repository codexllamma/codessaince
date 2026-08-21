import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import {
  ClipboardCheck,
  ShieldCheck,
  ShieldAlert,
  UserSquare2,
  Loader2,
  Video,
  Download,
  FileWarning,
  ListChecks,
  AlertTriangle,
} from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp, toLangCode } from '../../Context/AppContext'
import { api, type AvatarInfo, type FactCategory } from '../../api/client'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

const CATEGORY_LABEL: Record<FactCategory, string> = {
  SCHEME_NAME: 'Scheme name',
  AMOUNT: 'Amount',
  DEADLINE: 'Deadline',
  ELIGIBILITY: 'Eligibility',
  BENEFICIARY: 'Beneficiary',
  AUTHORITY: 'Authority',
  ACTION_REQUIRED: 'Action required',
}

const SOURCE_HINT: Record<string, string> = {
  synthetic: 'Synthetic — no real person depicted',
  licensed_stock: 'Licensed stock footage of a real person',
  consented_performer: 'Filmed with the performer’s consent',
}

const errMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

type ChecklistKey = 'facts' | 'disclosure' | 'release'

export default function OfficerApproval() {
  const navigate = useNavigate()
  const { jobId, job, setJob, selectedAvatar, targetLanguages, resetJob } = useApp()

  const [loadError, setLoadError] = useState<string | null>(null)

  const [avatars, setAvatars] = useState<AvatarInfo[] | null>(null)
  const [avatarError, setAvatarError] = useState<string | null>(null)

  const [checkedItems, setCheckedItems] = useState<Record<ChecklistKey, boolean>>({
    facts: false,
    disclosure: false,
    release: false,
  })
  const [notes, setNotes] = useState('')

  const [approving, setApproving] = useState(false)
  const [approveError, setApproveError] = useState<string | null>(null)

  const [rendering, setRendering] = useState(false)
  const [renderElapsed, setRenderElapsed] = useState(0)
  const [renderError, setRenderError] = useState<string | null>(null)

  // Recover the job payload if this screen is reached without one in context
  // (deep link, refresh) — same pattern as Storyboard and VoiceKaraoke.
  useEffect(() => {
    if (!jobId || job) return
    let cancelled = false
    api
      .getJob(jobId)
      .then((j) => {
        if (!cancelled) setJob(j)
      })
      .catch((e) => {
        if (!cancelled) {
          const msg = errMessage(e)
          setLoadError(msg)
          toast.error(`Could not load job: ${msg}`)
        }
      })
    return () => {
      cancelled = true
    }
  }, [jobId, job, setJob])

  // Registered presenters, needed to resolve the disclosure label for the
  // presenter chosen on the Voice step. An empty list is a legitimate
  // answer — it means no presenter is installed.
  useEffect(() => {
    let cancelled = false
    api
      .listAvatars()
      .then((list) => {
        if (!cancelled) setAvatars(list)
      })
      .catch((e) => {
        if (!cancelled) setAvatarError(errMessage(e))
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!rendering) return
    const started = Date.now()
    setRenderElapsed(0)
    const id = window.setInterval(() => setRenderElapsed(Math.round((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(id)
  }, [rendering])

  const activePresenter = (avatars || []).find((a) => a.avatar_id === selectedAvatar) || null
  const hasPresenterSelection = Boolean(selectedAvatar)

  const facts = job?.extracted_facts || []
  const allChecked = Object.values(checkedItems).every(Boolean)
  const isApproved = Boolean(job?.officer_approved)

  const primaryLanguage = targetLanguages[0] || null
  const primaryLangCode = primaryLanguage ? toLangCode(primaryLanguage) : null

  const videoPaths = job?.final_video_paths || {}
  const renderedForPrimary = primaryLangCode ? videoPaths[primaryLangCode] : undefined

  const toggleCheck = (key: ChecklistKey) => {
    if (isApproved) return
    setCheckedItems((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleApprove = useCallback(async () => {
    if (!jobId) return
    setApproving(true)
    setApproveError(null)
    try {
      const updated = await api.approveJob(jobId, notes.trim() || undefined)
      setJob(updated)
      if (updated.officer_approved) {
        toast.success('Officer approval recorded')
      } else {
        toast.warn('Approve call returned, but the job is not marked approved')
      }
    } catch (e) {
      const msg = errMessage(e)
      setApproveError(msg)
      toast.error(`Approval failed: ${msg}`)
    } finally {
      setApproving(false)
    }
  }, [jobId, notes, setJob])

  const handleRender = useCallback(async () => {
    if (!jobId || !primaryLangCode) return
    setRendering(true)
    setRenderError(null)
    try {
      const updated = await api.renderVideo(jobId, primaryLangCode, selectedAvatar || undefined)
      setJob(updated)
      if (updated.final_video_paths && updated.final_video_paths[primaryLangCode]) {
        toast.success('Video rendered successfully')
      } else {
        toast.warn('Render finished, but no video path came back for this language')
      }
    } catch (e) {
      const msg = errMessage(e)
      setRenderError(msg)
      toast.error(`Render failed: ${msg}`)
    } finally {
      setRendering(false)
    }
  }, [jobId, primaryLangCode, selectedAvatar, setJob])

  const startNew = () => {
    resetJob()
    navigate('/admin/upload')
  }

  if (!jobId) {
    return (
      <PageShell showBack backTo="/admin/voice-karaoke" wide>
        <div className="pt-4 sm:pt-8">
          <StepProgress steps={STEPS} current={6} />
          <div className="mt-8 flex items-center gap-2">
            <ClipboardCheck size={22} className="text-blossom-500" />
            <h1 className="font-display text-3xl font-semibold text-plum-900">Officer approval</h1>
          </div>
          <Card className="mt-7 text-center py-12">
            <FileWarning size={26} className="mx-auto text-blossom-500" />
            <p className="mt-3 font-display text-lg font-semibold text-plum-900">No notice ingested yet</p>
            <p className="mt-2 text-sm text-plum-800/60 max-w-md mx-auto">
              There is nothing to approve until a notice has been ingested, storyboarded and narrated. Start a
              new notice to reach this step.
            </p>
            <div className="mt-6 flex justify-center">
              <Button onClick={() => navigate('/admin/ingest')}>Go to notice ingest</Button>
            </div>
          </Card>
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell showBack backTo="/admin/voice-karaoke" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={6} />

        <div className="mt-8 flex items-center gap-2">
          <ClipboardCheck size={22} className="text-blossom-500" />
          <h1 className="font-display text-3xl font-semibold text-plum-900">Officer approval</h1>
        </div>
        <p className="mt-2 text-plum-800/70">
          A named officer signs off before any video is produced. This is the last gate before public dispatch.
        </p>

        {loadError && !job && (
          <Card className="mt-6 border border-red-200">
            <p className="text-sm font-medium text-red-600">Could not load this job</p>
            <p className="mt-1 text-xs text-plum-800/60 break-words">{loadError}</p>
          </Card>
        )}

        {job && (
          <div className="mt-7 grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* Extracted facts under review */}
              <Card strong>
                <div className="flex items-center gap-2">
                  <ListChecks size={16} className="text-blossom-500" />
                  <h2 className="text-sm font-semibold text-plum-900">Extracted facts under review</h2>
                </div>
                {facts.length === 0 ? (
                  <p className="mt-3 text-xs text-plum-800/55">
                    No extracted facts are attached to this job. There is nothing to verify here — go back and
                    run fact grounding first.
                  </p>
                ) : (
                  <div className="mt-4 space-y-2">
                    {facts.map((f) => (
                      <div
                        key={f.fact_id}
                        className="rounded-xl bg-white/60 border border-white/70 px-3 py-2.5 flex items-start justify-between gap-3"
                      >
                        <div className="min-w-0">
                          <span className="text-[10px] font-semibold uppercase tracking-wide text-blossom-600">
                            {CATEGORY_LABEL[f.category] || f.category}
                          </span>
                          <p dir="auto" className="mt-0.5 text-sm font-medium text-plum-900 break-words">
                            {f.normalized_value}
                          </p>
                          {f.officer_override && (
                            <p dir="auto" className="mt-0.5 text-xs text-skycandy-600 break-words">
                              Officer override: {f.officer_override}
                            </p>
                          )}
                        </div>
                        <span className="shrink-0 rounded-full bg-plum-900/5 px-2 py-1 text-[11px] font-mono text-plum-800/70">
                          {Math.round(f.confidence_score * 100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Mandatory on-screen presenter disclosure — always rendered in full. */}
              <Card strong>
                <div className="flex items-center gap-2">
                  <UserSquare2 size={16} className="text-blossom-500" />
                  <h2 className="text-sm font-semibold text-plum-900">On-screen presenter disclosure</h2>
                </div>

                {avatarError ? (
                  <div className="mt-3 rounded-xl border border-red-200 bg-white/60 p-3">
                    <p className="text-xs font-medium text-red-600">Could not load presenter details</p>
                    <p className="mt-1 text-[11px] text-plum-800/60 break-words">{avatarError}</p>
                  </div>
                ) : avatars === null ? (
                  <div className="mt-3 flex items-center gap-2 text-xs text-plum-800/60">
                    <Loader2 size={14} className="animate-spin text-blossom-500" /> Loading presenter details…
                  </div>
                ) : !hasPresenterSelection ? (
                  <p className="mt-3 text-xs text-plum-800/60 leading-relaxed">
                    No on-screen presenter was chosen on the Voice step. Videos will render in the full-width
                    layout with no on-screen presenter and no disclosure label is applicable.
                  </p>
                ) : activePresenter ? (
                  <div className="mt-3 space-y-2">
                    <p className="text-sm font-medium text-plum-900">{activePresenter.display_name}</p>
                    {/* The disclosure label itself — non-negotiable, shown in full. */}
                    <p className="rounded-xl bg-orange-100 px-3 py-2 text-xs font-semibold leading-snug text-orange-700 break-words">
                      {activePresenter.disclosure_label}
                    </p>
                    <p className="text-[11px] text-plum-800/60">
                      {SOURCE_HINT[activePresenter.source] || activePresenter.source} ·{' '}
                      {activePresenter.languages.join(', ')}
                    </p>
                    {activePresenter.licence.startsWith('UNCONFIRMED') && (
                      <p className="inline-flex items-center gap-1 text-[11px] font-medium text-red-600">
                        <ShieldAlert size={12} /> Licence unconfirmed — resolve before public dispatch.
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-red-600 leading-relaxed">
                    A presenter (id: {selectedAvatar}) was selected on the Voice step, but it is not in the
                    backend's current presenter list — its disclosure label cannot be verified here. Go back to
                    Voice and re-select a presenter before approving.
                  </p>
                )}
              </Card>
            </div>

            {/* Sign-off + render */}
            <div className="space-y-6">
              {!isApproved ? (
                <Card strong className="space-y-4">
                  <div className="flex items-center gap-2">
                    <ShieldAlert size={16} className="text-blossom-500" />
                    <h2 className="text-sm font-semibold text-plum-900">Officer sign-off</h2>
                  </div>

                  <div className="space-y-2.5">
                    <label
                      className={`flex items-start gap-2.5 rounded-xl border p-3 cursor-pointer transition-colors ${
                        checkedItems.facts ? 'border-blossom-300 bg-blossom-50/70' : 'border-white/70 bg-white/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checkedItems.facts}
                        onChange={() => toggleCheck('facts')}
                        className="mt-0.5 accent-blossom-500 h-4 w-4"
                      />
                      <span className="text-xs text-plum-800/80">I have reviewed the extracted facts</span>
                    </label>

                    <label
                      className={`flex items-start gap-2.5 rounded-xl border p-3 cursor-pointer transition-colors ${
                        checkedItems.disclosure ? 'border-blossom-300 bg-blossom-50/70' : 'border-white/70 bg-white/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checkedItems.disclosure}
                        onChange={() => toggleCheck('disclosure')}
                        className="mt-0.5 accent-blossom-500 h-4 w-4"
                      />
                      <span className="text-xs text-plum-800/80">
                        I confirm the presenter disclosure is accurate
                      </span>
                    </label>

                    <label
                      className={`flex items-start gap-2.5 rounded-xl border p-3 cursor-pointer transition-colors ${
                        checkedItems.release ? 'border-blossom-300 bg-blossom-50/70' : 'border-white/70 bg-white/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checkedItems.release}
                        onChange={() => toggleCheck('release')}
                        className="mt-0.5 accent-blossom-500 h-4 w-4"
                      />
                      <span className="text-xs text-plum-800/80">I approve this video for release</span>
                    </label>
                  </div>

                  <div>
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-plum-800/50">
                      Officer notes (optional)
                    </label>
                    <input
                      type="text"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="e.g. Verified against the gazette notification..."
                      disabled={approving}
                      className="mt-1.5 w-full rounded-xl bg-white/60 border border-white/70 px-3 py-2 text-xs text-plum-900 focus:outline-none focus:border-blossom-400 disabled:opacity-60"
                    />
                  </div>

                  {approveError && (
                    <p className="text-xs text-red-600 break-words">Approval failed: {approveError}</p>
                  )}

                  <Button
                    className="w-full"
                    onClick={() => void handleApprove()}
                    disabled={!allChecked || approving}
                    icon={approving ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                  >
                    {approving ? 'Recording approval…' : 'Grant officer approval'}
                  </Button>
                </Card>
              ) : (
                <Card strong className="space-y-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={16} className="text-blossom-500" />
                    <h2 className="text-sm font-semibold text-plum-900">Approval recorded</h2>
                  </div>
                  <p className="text-xs text-plum-800/60">
                    This job is digitally signed as officer-approved. Final rendering is unlocked below.
                  </p>

                  {rendering && (
                    <div className="rounded-2xl bg-white/60 p-3.5 flex items-start gap-2.5">
                      <Loader2 size={16} className="animate-spin text-blossom-500 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-medium text-plum-900">
                          Rendering video… {fmt(renderElapsed)} elapsed
                        </p>
                        <p className="mt-0.5 text-[11px] text-plum-800/55">
                          Narration synthesis, lip-sync and video encoding run server-side. This can take several
                          minutes — there is no percentage to show, only elapsed time. Controls stay disabled
                          until it returns.
                        </p>
                      </div>
                    </div>
                  )}

                  {renderError && !rendering && (
                    <div className="rounded-xl border border-red-200 bg-white/60 p-3">
                      <p className="text-xs font-medium text-red-600">Render failed</p>
                      <p className="mt-1 text-[11px] text-plum-800/60 break-words">{renderError}</p>
                    </div>
                  )}

                  {!primaryLangCode && (
                    <p className="inline-flex items-center gap-1.5 text-[11px] font-medium text-orange-600">
                      <AlertTriangle size={12} /> No target language is set on this job — pick one before
                      rendering.
                    </p>
                  )}

                  <Button
                    className="w-full"
                    onClick={() => void handleRender()}
                    disabled={rendering || !primaryLangCode}
                    icon={rendering ? <Loader2 size={16} className="animate-spin" /> : <Video size={16} />}
                  >
                    {rendering ? 'Rendering…' : renderedForPrimary ? 'Re-render video' : 'Render final video'}
                  </Button>
                </Card>
              )}

              {renderedForPrimary && primaryLangCode && (
                <Card strong className="space-y-3">
                  <div className="flex items-center gap-2">
                    <Video size={16} className="text-blossom-500" />
                    <h2 className="text-sm font-semibold text-plum-900">
                      Rendered video · {primaryLanguage}
                    </h2>
                  </div>
                  <div className="rounded-2xl overflow-hidden bg-black aspect-video">
                    <video
                      key={renderedForPrimary}
                      controls
                      className="w-full h-full"
                      src={api.getVideoUrl(renderedForPrimary)}
                    >
                      Your browser does not support HTML5 video playback.
                    </video>
                  </div>
                  <a
                    href={api.getVideoUrl(renderedForPrimary)}
                    download={`VaaniReach_${job.job_id}_${primaryLangCode}.mp4`}
                    className="inline-flex items-center justify-center gap-2 w-full rounded-full bg-gradient-to-r from-blossom-700 to-blossom-800 text-plum-900 shadow-glow px-6 py-3 text-sm font-medium hover:brightness-105 transition-all"
                  >
                    <Download size={16} />
                    Download rendered MP4
                  </a>
                </Card>
              )}
            </div>
          </div>
        )}

        {job && renderedForPrimary && (
          <div className="mt-10 text-center">
            <Button variant="ghost" onClick={startNew}>
              Process another notice
            </Button>
          </div>
        )}
      </div>
    </PageShell>
  )
}
