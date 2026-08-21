import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import gsap from 'gsap'
import { Clapperboard, ImageIcon, Loader2, RefreshCw, ShieldCheck, MessageSquare, FileWarning } from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp, toLangCode } from '../../Context/AppContext'
import { api, type SceneDefinition, type ScriptSegment } from '../../api/client'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

/** Purely presentational: the backend picks the template, this picks the swatch. */
const TEMPLATE_VISUAL: Record<SceneDefinition['template_type'], string> = {
  HERO_ANNOUNCEMENT: 'from-blossom-200 to-peachcandy/70',
  METRIC_FOCUS: 'from-skycandy-200 to-lavendercandy/70',
  DEADLINE_ALERT: 'from-peachcandy/70 to-blossom-200',
  OUTRO_CALL_TO_ACTION: 'from-lavendercandy/70 to-skycandy-200',
}

const TEMPLATE_LABEL: Record<SceneDefinition['template_type'], string> = {
  HERO_ANNOUNCEMENT: 'Hero announcement',
  METRIC_FOCUS: 'Metric focus',
  DEADLINE_ALERT: 'Deadline alert',
  OUTRO_CALL_TO_ACTION: 'Call to action',
}

const errMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))

function SegmentLine({ segment }: { segment: ScriptSegment }) {
  const isCore = segment.type === 'core_fact'
  return (
    <div
      className={`rounded-xl px-3 py-2 text-sm leading-relaxed ${
        isCore
          ? 'bg-blossom-50 border border-blossom-200 text-plum-900 font-medium'
          : 'bg-white/50 border border-white/70 text-plum-800/60'
      }`}
    >
      <div className="flex items-center gap-1.5 mb-1">
        {isCore ? (
          <>
            <ShieldCheck size={12} className="text-blossom-600 shrink-0" />
            <span className="text-[10px] font-semibold uppercase tracking-wide text-blossom-600">
              Core fact
            </span>
          </>
        ) : (
          <>
            <MessageSquare size={12} className="text-plum-800/40 shrink-0" />
            <span className="text-[10px] font-semibold uppercase tracking-wide text-plum-800/40">
              Filler
            </span>
          </>
        )}
        {segment.emphasis_level && segment.emphasis_level !== 'none' && (
          <span className="text-[10px] text-skycandy-500 font-medium">· emphasis: {segment.emphasis_level}</span>
        )}
        {typeof segment.pause_after_ms === 'number' && segment.pause_after_ms > 0 && (
          <span className="text-[10px] text-plum-800/40">· pause {segment.pause_after_ms}ms</span>
        )}
      </div>
      <p dir="auto">{segment.text}</p>
    </div>
  )
}

export default function StoryBoard() {
  const navigate = useNavigate()
  const { targetLanguages, jobId, job, setJob } = useApp()

  const languages = ['English', ...targetLanguages.filter((l) => l !== 'English')]
  const [activeLang, setActiveLang] = useState(languages[0] ?? 'English')
  const selectedLang = languages.includes(activeLang) ? activeLang : languages[0] ?? 'English'

  const [generating, setGenerating] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const gridRef = useRef<HTMLDivElement>(null)
  const autoRan = useRef(false)

  const scenesFor = (label: string): SceneDefinition[] => {
    if (!job) return []
    if (label === 'English') return job.master_scenes_en || []
    return (job.localized_scenes && job.localized_scenes[toLangCode(label)]) || []
  }

  const scenes = scenesFor(selectedLang)
  const masterCount = job?.master_scenes_en?.length || 0

  const generate = useCallback(
    async (announce: boolean) => {
      if (!jobId) return
      setGenerating(true)
      setLoadError(null)
      try {
        const updated = await api.generateScenes(jobId)
        setJob(updated)
        const count = updated.master_scenes_en?.length || 0
        if (count === 0) {
          toast.warn('The backend returned no scenes for this notice')
        } else if (announce) {
          toast.success(`${count} scene${count === 1 ? '' : 's'} generated`)
        }
      } catch (e) {
        const msg = errMessage(e)
        setLoadError(msg)
        toast.error(`Scene generation failed: ${msg}`)
      } finally {
        setGenerating(false)
      }
    },
    [jobId, setJob]
  )

  // Recover the job payload if this screen is reached without one in context.
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

  // Generate once, automatically, when the job has no scenes yet.
  useEffect(() => {
    if (!jobId || !job || autoRan.current) return
    if ((job.master_scenes_en?.length || 0) > 0) {
      autoRan.current = true
      return
    }
    autoRan.current = true
    void generate(false)
  }, [jobId, job, generate])

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.scene-card', { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.35, stagger: 0.07, ease: 'power2.out' })
    }, gridRef)
    return () => ctx.revert()
  }, [selectedLang, scenes.length])

  if (!jobId) {
    return (
      <PageShell showBack backTo="/admin/fact-grounding" wide>
        <div className="pt-4 sm:pt-8">
          <StepProgress steps={STEPS} current={4} />
          <div className="mt-8 flex items-center gap-2">
            <Clapperboard size={22} className="text-blossom-500" />
            <h1 className="font-display text-3xl font-semibold text-plum-900">Storyboard</h1>
          </div>
          <Card className="mt-7 text-center py-12">
            <FileWarning size={26} className="mx-auto text-blossom-500" />
            <p className="mt-3 font-display text-lg font-semibold text-plum-900">No notice ingested yet</p>
            <p className="mt-2 text-sm text-plum-800/60 max-w-md mx-auto">
              A storyboard can only be built from a notice that has been ingested and fact-grounded. Nothing
              is shown here until that job exists.
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
    <PageShell showBack backTo="/admin/fact-grounding" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={4} />

        <div className="mt-8 flex items-center gap-2">
          <Clapperboard size={22} className="text-blossom-500" />
          <h1 className="font-display text-3xl font-semibold text-plum-900">Storyboard</h1>
        </div>
        <p className="mt-2 text-plum-800/70">
          {masterCount > 0
            ? `${masterCount} scene${masterCount === 1 ? '' : 's'} generated from the grounded facts. Switch languages to review each cut.`
            : 'Scenes are generated from the grounded facts of this notice.'}
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          {languages.map((l) => {
            const count = scenesFor(l).length
            return (
              <button
                key={l}
                onClick={() => setActiveLang(l)}
                disabled={generating}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all disabled:opacity-50 ${
                  selectedLang === l ? 'bg-linear-to-r from-blossom-400 to-blossom-500 text-white shadow-glow' : 'glass text-plum-800/70 hover:bg-blossom-50'
                }`}
              >
                {l}
                <span className="ml-1.5 text-[11px] opacity-70">{count}</span>
              </button>
            )
          })}

          <button
            onClick={() => void generate(true)}
            disabled={generating}
            className="ml-auto inline-flex items-center gap-1.5 rounded-full glass px-4 py-2 text-sm font-medium text-plum-800/70 hover:bg-blossom-50 transition-colors disabled:opacity-50"
          >
            {generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {generating ? 'Generating scenes…' : masterCount > 0 ? 'Regenerate scenes' : 'Generate scenes'}
          </button>
        </div>

        {generating && (
          <Card className="mt-6 flex items-center gap-3">
            <Loader2 size={18} className="animate-spin text-blossom-500 shrink-0" />
            <div>
              <p className="text-sm font-medium text-plum-900">Generating scenes and translations…</p>
              <p className="text-xs text-plum-800/55">
                The backend scripts every scene and translates it into each target language. This can take a
                while — controls stay disabled until it returns.
              </p>
            </div>
          </Card>
        )}

        {loadError && !generating && (
          <Card className="mt-6 border border-red-200">
            <p className="text-sm font-medium text-red-600">Scene generation failed</p>
            <p className="mt-1 text-xs text-plum-800/60 break-words">{loadError}</p>
          </Card>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-plum-800/60">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded bg-blossom-50 border border-blossom-200" />
            <ShieldCheck size={12} className="text-blossom-600" /> Core fact — grounded in the notice
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded bg-white/50 border border-white/70" />
            <MessageSquare size={12} className="text-plum-800/40" /> Filler — connective narration
          </span>
        </div>

        <div ref={gridRef} className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-5">
          {scenes.map((scene) => {
            const vh = scene.visual_hierarchy
            const coreCount = (scene.script_segments || []).filter((s) => s.type === 'core_fact').length
            return (
              <Card key={`${selectedLang}-${scene.scene_id}`} className="scene-card p-0 overflow-hidden">
                <div
                  className={`relative aspect-video bg-linear-to-br ${
                    TEMPLATE_VISUAL[scene.template_type] || 'from-blossom-200 to-skycandy-200'
                  } flex flex-col items-center justify-center px-6 text-center`}
                >
                  <span className="absolute top-3 left-3 rounded-full bg-white/70 px-2.5 py-1 text-[11px] font-semibold text-plum-800">
                    Scene {scene.scene_id}
                  </span>
                  <span className="absolute top-3 right-3 rounded-full bg-white/70 px-2.5 py-1 text-[11px] font-semibold text-plum-800">
                    {TEMPLATE_LABEL[scene.template_type] || scene.template_type}
                  </span>

                  {vh ? (
                    <>
                      {vh.badge_tag && (
                        <span className="rounded-full bg-white/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-plum-800">
                          {vh.badge_tag}
                        </span>
                      )}
                      <p dir="auto" className="mt-2 font-display text-lg font-semibold leading-snug text-plum-900">
                        {vh.headline}
                      </p>
                      {vh.subtext && (
                        <p dir="auto" className="mt-1 text-xs text-plum-900/70 leading-relaxed">
                          {vh.subtext}
                        </p>
                      )}
                      {vh.highlight_metric && (
                        <div className="mt-3 rounded-2xl bg-white/70 px-4 py-2">
                          <p dir="auto" className="font-display text-xl font-semibold text-plum-900">
                            {vh.highlight_metric}
                          </p>
                          {vh.highlight_sublabel && (
                            <p dir="auto" className="text-[10px] uppercase tracking-wide text-plum-800/60">
                              {vh.highlight_sublabel}
                            </p>
                          )}
                        </div>
                      )}
                    </>
                  ) : (
                    <ImageIcon size={26} className="text-white/80" />
                  )}
                </div>

                <div className="p-4 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-plum-800/50">
                      Script
                    </span>
                    <span className="text-[11px] text-plum-800/50">
                      {coreCount} core fact{coreCount === 1 ? '' : 's'} of {(scene.script_segments || []).length} segment
                      {(scene.script_segments || []).length === 1 ? '' : 's'}
                    </span>
                  </div>

                  {(scene.script_segments || []).length > 0 ? (
                    <div className="space-y-2">
                      {scene.script_segments.map((seg, i) => (
                        <SegmentLine key={i} segment={seg} />
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-plum-800/50 italic">No script segments returned for this scene.</p>
                  )}

                  {scene.full_spoken_text && (
                    <details className="rounded-xl bg-white/50 px-3 py-2">
                      <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wide text-plum-800/50">
                        Full spoken line
                      </summary>
                      <p dir="auto" className="mt-2 text-sm leading-relaxed text-plum-900">
                        {scene.full_spoken_text}
                      </p>
                    </details>
                  )}
                </div>
              </Card>
            )
          })}
        </div>

        {!generating && scenes.length === 0 && (
          <Card className="mt-6 text-center py-10">
            <FileWarning size={24} className="mx-auto text-blossom-500" />
            <p className="mt-3 text-sm font-medium text-plum-900">
              {masterCount === 0
                ? 'No scenes have been generated for this notice yet.'
                : `No ${selectedLang} scenes came back from the backend.`}
            </p>
            <p className="mt-1 text-xs text-plum-800/55 max-w-md mx-auto">
              {masterCount === 0
                ? 'Use “Generate scenes” above to build the storyboard from the grounded facts.'
                : 'The master (English) storyboard exists, but this language has no localized scenes in the job payload.'}
            </p>
          </Card>
        )}

        <div className="mt-10 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-sm text-plum-800/60">
            {scenes.length} scene{scenes.length === 1 ? '' : 's'} shown for {selectedLang}
          </p>
          <Button onClick={() => navigate('/admin/voice-karaoke')} disabled={generating || masterCount === 0}>
            Continue to voice and karaoke
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
