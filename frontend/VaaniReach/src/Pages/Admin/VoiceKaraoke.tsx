import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import gsap from 'gsap'
import {
  Play,
  Pause,
  Mic2,
  Gauge,
  Sparkles,
  Loader2,
  AudioWaveform,
  UserSquare2,
  ShieldAlert,
  Check,
  FileWarning,
} from 'lucide-react'
import PageShell from '../../Components/PageShell'
import Card from '../../Components/UI/Card'
import Button from '../../Components/UI/Button'
import StepProgress from '../../Components/UI/StepProgress'
import { useApp, toLangCode } from '../../Context/AppContext'
import { api, type AvatarInfo, type SceneDefinition } from '../../api/client'

const STEPS = ['Upload', 'Categorize', 'Ingest', 'Fact grounding', 'Storyboard', 'Voice', 'Approval']

const SOURCE_HINT: Record<string, string> = {
  synthetic: 'Synthetic — no real person depicted',
  licensed_stock: 'Licensed stock footage of a real person',
  consented_performer: 'Filmed with the performer’s consent',
}

const GESTURE_ROLE_HINT: Record<string, string> = {
  neutral: 'resting pose',
  present: 'on core facts',
  stress: 'on deadline scenes',
}

const errMessage = (e: unknown) => (e instanceof Error ? e.message : String(e))
const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

export default function VoiceKaraoke() {
  const navigate = useNavigate()
  const {
    targetLanguages,
    jobId,
    job,
    setJob,
    selectedAvatar,
    setSelectedAvatar,
    setSelectedVoice,
  } = useApp()

  const [avatars, setAvatars] = useState<AvatarInfo[] | null>(null)
  const [avatarError, setAvatarError] = useState<string | null>(null)

  const [synthesizing, setSynthesizing] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [synthError, setSynthError] = useState<string | null>(null)

  const languages = ['English', ...targetLanguages.filter((l) => l !== 'English')]
  const [activeLang, setActiveLang] = useState(languages[0] ?? 'English')
  const selectedLang = languages.includes(activeLang) ? activeLang : languages[0] ?? 'English'

  const [sceneIndex, setSceneIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)

  const audioRef = useRef<HTMLAudioElement | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const scenesFor = (label: string): SceneDefinition[] => {
    if (!job) return []
    if (label === 'English') return job.master_scenes_en || []
    return (job.localized_scenes && job.localized_scenes[toLangCode(label)]) || []
  }

  const scenes = scenesFor(selectedLang)
  const scene: SceneDefinition | undefined = scenes[sceneIndex]
  const subtitles = scene?.subtitles || []
  const hasAudio = Boolean(scene?.audio_path)

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
        if (!cancelled) toast.error(`Could not load job: ${errMessage(e)}`)
      })
    return () => {
      cancelled = true
    }
  }, [jobId, job, setJob])

  // The narration voice id is fixed when the job is created; surface the real
  // value rather than inventing a picker the backend has no route for.
  useEffect(() => {
    if (job?.selected_voice_id) setSelectedVoice(job.selected_voice_id)
  }, [job?.selected_voice_id, setSelectedVoice])

  // Registered presenters. An empty list is a legitimate answer: it means no
  // presenter is installed and the compositor renders full-width instead.
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

  // An avatar fronts a language if it lists the code, or claims the catch-all.
  const jobLangCodes = job?.target_languages?.length
    ? job.target_languages
    : languages.map((l) => toLangCode(l))
  const matching = (avatars || []).filter((a) =>
    jobLangCodes.some((l) => a.languages.includes(l) || a.languages.includes('*'))
  )
  const presenters = matching.length > 0 ? matching : avatars || []
  const noLanguageMatch = (avatars || []).length > 0 && matching.length === 0
  const activePresenter = presenters.find((a) => a.avatar_id === selectedAvatar) || null

  const firstPresenterId = presenters.length > 0 ? presenters[0].avatar_id : ''
  useEffect(() => {
    if (!selectedAvatar && firstPresenterId) setSelectedAvatar(firstPresenterId)
  }, [selectedAvatar, firstPresenterId, setSelectedAvatar])

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.fromTo('.voice-card', { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: 0.35, stagger: 0.06, ease: 'power2.out' })
    }, listRef)
    return () => ctx.revert()
  }, [avatars])

  // Reset playback whenever the previewed clip changes.
  useEffect(() => {
    const el = audioRef.current
    if (el) {
      el.pause()
      el.currentTime = 0
    }
    setPlaying(false)
    setCurrentTime(0)
    setDuration(0)
  }, [selectedLang, sceneIndex, scene?.audio_path])

  useEffect(() => {
    setSceneIndex(0)
  }, [selectedLang])

  useEffect(() => {
    if (!synthesizing) return
    const started = Date.now()
    setElapsed(0)
    const id = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(id)
  }, [synthesizing])

  const synthesize = useCallback(async () => {
    if (!jobId) return
    setSynthesizing(true)
    setSynthError(null)
    try {
      const updated = await api.synthesizeAudio(jobId)
      setJob(updated)
      const withAudio = (updated.master_scenes_en || []).filter((s) => s.audio_path).length
      if (withAudio === 0) {
        toast.warn('Synthesis returned, but no scene carries an audio path')
      } else {
        toast.success(`Narration synthesized for ${withAudio} scene${withAudio === 1 ? '' : 's'}`)
      }
    } catch (e) {
      const msg = errMessage(e)
      setSynthError(msg)
      toast.error(`Synthesis failed: ${msg}`)
    } finally {
      setSynthesizing(false)
    }
  }, [jobId, setJob])

  const togglePlay = () => {
    const el = audioRef.current
    if (!el) return
    if (playing) {
      el.pause()
      setPlaying(false)
      return
    }
    el.play()
      .then(() => setPlaying(true))
      .catch((e) => {
        setPlaying(false)
        toast.error(`Could not play narration: ${errMessage(e)}`)
      })
  }

  const activeWord = subtitles.findIndex((w) => currentTime >= w.start_sec && currentTime < w.end_sec)
  const progressPct = duration > 0 ? Math.min(100, (currentTime / duration) * 100) : 0
  const controlsLocked = synthesizing

  if (!jobId) {
    return (
      <PageShell showBack backTo="/admin/storyboard" wide>
        <div className="pt-4 sm:pt-8">
          <StepProgress steps={STEPS} current={5} />
          <div className="mt-8 flex items-center gap-2">
            <Mic2 size={22} className="text-blossom-500" />
            <h1 className="font-display text-3xl font-semibold text-plum-900">Voice and karaoke</h1>
          </div>
          <Card className="mt-7 text-center py-12">
            <FileWarning size={26} className="mx-auto text-blossom-500" />
            <p className="mt-3 font-display text-lg font-semibold text-plum-900">No notice ingested yet</p>
            <p className="mt-2 text-sm text-plum-800/60 max-w-md mx-auto">
              Narration is synthesized from a real job’s scenes. There is nothing to voice until a notice has
              been ingested and storyboarded.
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
    <PageShell showBack backTo="/admin/storyboard" wide>
      <div className="pt-4 sm:pt-8">
        <StepProgress steps={STEPS} current={5} />

        <div className="mt-8 flex items-center gap-2">
          <Mic2 size={22} className="text-blossom-500" />
          <h1 className="font-display text-3xl font-semibold text-plum-900">Voice and karaoke</h1>
        </div>
        <p className="mt-2 text-plum-800/70">Neural narration with word-level timing, generated for accessible captions.</p>

        {synthesizing && (
          <Card className="mt-6 flex items-center gap-3">
            <Loader2 size={18} className="animate-spin text-blossom-500 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-plum-900">Synthesizing narration… {fmt(elapsed)} elapsed</p>
              <p className="text-xs text-plum-800/55">
                Every scene in every target language is spoken and force-aligned to word timings. There is no
                progress feed from the backend, so this shows elapsed time only. Controls stay disabled until
                it returns.
              </p>
            </div>
          </Card>
        )}

        {synthError && !synthesizing && (
          <Card className="mt-6 border border-red-200">
            <p className="text-sm font-medium text-red-600">Synthesis failed</p>
            <p className="mt-1 text-xs text-plum-800/60 break-words">{synthError}</p>
          </Card>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-2">
          {languages.map((l) => (
            <button
              key={l}
              onClick={() => setActiveLang(l)}
              disabled={controlsLocked}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-all disabled:opacity-50 ${
                selectedLang === l ? 'bg-linear-to-r from-blossom-400 to-blossom-500 text-white shadow-glow' : 'glass text-plum-800/70 hover:bg-blossom-50'
              }`}
            >
              {l}
            </button>
          ))}
        </div>

        <div className="mt-7 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card strong className="lg:col-span-2">
            {scenes.length === 0 ? (
              <div className="py-10 text-center">
                <FileWarning size={22} className="mx-auto text-blossom-500" />
                <p className="mt-3 text-sm font-medium text-plum-900">No {selectedLang} scenes in this job</p>
                <p className="mt-1 text-xs text-plum-800/55">
                  Generate the storyboard first — narration is spoken from those scenes.
                </p>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  {scenes.map((s, i) => (
                    <button
                      key={s.scene_id}
                      onClick={() => setSceneIndex(i)}
                      disabled={controlsLocked}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                        i === sceneIndex ? 'bg-blossom-400 text-white' : 'bg-blossom-50 text-plum-800/70 hover:bg-blossom-100'
                      }`}
                    >
                      Scene {s.scene_id}
                      {s.audio_path ? <AudioWaveform size={11} className="ml-1 inline" /> : null}
                    </button>
                  ))}
                </div>

                <div className="mt-5 flex items-center gap-4">
                  <button
                    onClick={togglePlay}
                    disabled={!hasAudio || controlsLocked}
                    className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-blossom-400 to-blossom-500 text-white shadow-glow hover:scale-105 transition-transform disabled:opacity-40 disabled:hover:scale-100"
                    aria-label={playing ? 'Pause narration' : 'Play narration'}
                  >
                    {playing ? <Pause size={22} /> : <Play size={22} className="ml-0.5" />}
                  </button>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-plum-900">
                      {job?.selected_voice_id || 'voice not set on job'}
                      {job?.voice_speed_modifier ? ` · ${job.voice_speed_modifier}` : ''}
                    </p>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blossom-50">
                      <div
                        className="h-full rounded-full bg-linear-to-r from-blossom-400 to-skycandy-400 transition-[width] duration-100"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                    <p className="mt-1 text-[11px] text-plum-800/50">
                      {hasAudio
                        ? `${currentTime.toFixed(1)}s / ${duration ? duration.toFixed(1) : '—'}s · audio from backend`
                        : 'No audio for this scene yet — run synthesis to generate it.'}
                    </p>
                  </div>
                </div>

                {hasAudio && (
                  <audio
                    ref={audioRef}
                    src={api.getAudioUrl(scene?.audio_path || '')}
                    preload="metadata"
                    onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                    onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
                    onEnded={() => {
                      setPlaying(false)
                      setCurrentTime(0)
                    }}
                    onError={() => {
                      setPlaying(false)
                      toast.error('Narration audio could not be loaded from the backend')
                    }}
                    className="hidden"
                  />
                )}

                <div className="mt-8 rounded-2xl bg-white/60 p-6 leading-loose text-lg sm:text-xl font-display">
                  {subtitles.length > 0 ? (
                    subtitles.map((w, i) => (
                      <span
                        key={i}
                        dir="auto"
                        title={`${w.start_sec.toFixed(2)}s – ${w.end_sec.toFixed(2)}s${w.is_core_fact ? ' · core fact' : ''}`}
                        className={`transition-colors duration-150 ${
                          i === activeWord
                            ? 'text-blossom-600 font-semibold'
                            : activeWord >= 0 && i < activeWord
                            ? 'text-plum-900/80'
                            : 'text-plum-800/35'
                        } ${w.is_core_fact ? 'underline decoration-blossom-300 decoration-2 underline-offset-4' : ''}`}
                      >
                        {w.word}{' '}
                      </span>
                    ))
                  ) : (
                    <p dir="auto" className="text-base text-plum-800/60">
                      {scene?.full_spoken_text || 'This scene has no spoken text.'}
                    </p>
                  )}
                </div>

                {subtitles.length === 0 && (
                  <p className="mt-2 text-xs text-plum-800/50">
                    No word timings returned for this scene yet — the line above is the script, not a timed
                    caption.
                  </p>
                )}

                {subtitles.length > 0 && (
                  <details className="mt-3 rounded-2xl bg-white/50 px-4 py-3">
                    <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-wide text-plum-800/50">
                      Word timings from the backend ({subtitles.length} words)
                    </summary>
                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-1.5 font-mono text-[11px]">
                      {subtitles.map((w, i) => (
                        <div
                          key={i}
                          className={`rounded-lg px-2 py-1 ${
                            w.is_core_fact ? 'bg-blossom-50 text-plum-900' : 'bg-white/70 text-plum-800/60'
                          }`}
                        >
                          <span dir="auto">{w.word}</span>{' '}
                          <span className="opacity-60">
                            {w.start_sec.toFixed(2)}–{w.end_sec.toFixed(2)}s
                          </span>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </>
            )}
          </Card>

          <div ref={listRef} className="space-y-6">
            <Card className="voice-card space-y-4 h-fit">
              <div className="flex items-center gap-2">
                <UserSquare2 size={15} className="text-blossom-500" />
                <h3 className="text-sm font-semibold text-plum-900">On-screen presenter</h3>
              </div>

              {avatarError ? (
                <div className="rounded-2xl border border-red-200 bg-white/60 p-3">
                  <p className="text-xs font-medium text-red-600">Could not load presenters</p>
                  <p className="mt-1 text-[11px] text-plum-800/60 break-words">{avatarError}</p>
                </div>
              ) : avatars === null ? (
                <div className="flex items-center gap-2 text-xs text-plum-800/60">
                  <Loader2 size={14} className="animate-spin text-blossom-500" /> Loading presenters…
                </div>
              ) : presenters.length === 0 ? (
                <p className="text-xs text-plum-800/60 leading-relaxed">
                  No presenter is installed on the backend. Videos render in the full-width layout with no
                  on-screen presenter.
                </p>
              ) : (
                <>
                  {noLanguageMatch && (
                    <p className="text-[11px] text-orange-600 leading-relaxed">
                      No installed presenter lists this job’s languages. All registered presenters are shown
                      below.
                    </p>
                  )}
                  <div className="space-y-3">
                    {presenters.map((a) => {
                      const active = selectedAvatar === a.avatar_id
                      return (
                        <button
                          key={a.avatar_id}
                          onClick={() => {
                            setSelectedAvatar(a.avatar_id)
                            if (job?.selected_voice_id) setSelectedVoice(job.selected_voice_id)
                          }}
                          disabled={controlsLocked}
                          className={`w-full text-left rounded-2xl border p-3 transition-all disabled:opacity-50 ${
                            active
                              ? 'border-blossom-400 ring-2 ring-blossom-300 bg-blossom-50/70'
                              : 'border-white/70 bg-white/50 hover:bg-blossom-50/60'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-medium text-plum-900">{a.display_name}</span>
                            {active && (
                              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blossom-500 text-white shrink-0">
                                <Check size={12} />
                              </span>
                            )}
                          </div>

                          {/* Mandatory transparency notice — always rendered in full. */}
                          <p className="mt-2 rounded-xl bg-orange-100 px-2.5 py-1.5 text-[11px] font-semibold leading-snug text-orange-700 break-words">
                            {a.disclosure_label}
                          </p>

                          <p className="mt-2 text-[11px] text-plum-800/60">
                            {SOURCE_HINT[a.source] || a.source} · {a.languages.join(', ')}
                          </p>
                          <p className="mt-0.5 text-[11px] text-plum-800/45 break-words">Licence: {a.licence}</p>
                          {a.licence.startsWith('UNCONFIRMED') && (
                            <p className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-red-600">
                              <ShieldAlert size={12} /> Licence unconfirmed — resolve before public dispatch.
                            </p>
                          )}
                          <p className="mt-1 text-[11px] text-plum-800/45">
                            {a.gestures.length === 0
                              ? 'No gesture sidecar — the presenter loops.'
                              : a.gestures
                                  .map((g) => `${g.name} (${GESTURE_ROLE_HINT[g.role] || g.role})`)
                                  .join(', ')}
                          </p>
                        </button>
                      )
                    })}
                  </div>
                </>
              )}
            </Card>

            <Card className="voice-card space-y-4 h-fit">
              <div className="flex items-center gap-2">
                <Mic2 size={15} className="text-blossom-500" />
                <h3 className="text-sm font-semibold text-plum-900">Narrator voice</h3>
              </div>
              <div className="rounded-2xl bg-white/60 p-3">
                <p className="font-mono text-xs text-plum-900 break-words">
                  {job?.selected_voice_id || 'Not set on this job'}
                </p>
                <p className="mt-1 text-[11px] text-plum-800/50">
                  Fixed when the job was created — the backend exposes no route to change it from here.
                </p>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <Gauge size={15} className="text-skycandy-500" />
                <h3 className="text-sm font-semibold text-plum-900">Speaking speed</h3>
              </div>
              <div className="rounded-2xl bg-white/60 p-3">
                <p className="font-mono text-xs text-plum-900">
                  {job?.voice_speed_modifier || 'Not set on this job'}
                </p>
                <p className="mt-1 text-[11px] text-plum-800/50">Value the backend will pass to Edge-TTS.</p>
              </div>

              <Button
                className="w-full"
                onClick={() => void synthesize()}
                disabled={controlsLocked || scenes.length === 0}
                icon={synthesizing ? <Loader2 size={16} className="animate-spin" /> : <AudioWaveform size={16} />}
              >
                {synthesizing ? 'Synthesizing…' : hasAudio ? 'Re-synthesize narration' : 'Synthesize narration'}
              </Button>

              <div className="rounded-2xl bg-blossom-50/70 p-4 flex items-start gap-2">
                <Sparkles size={15} className="text-blossom-500 mt-0.5 shrink-0" />
                <p className="text-xs text-plum-800/70 leading-relaxed">
                  {activePresenter
                    ? `${activePresenter.display_name} will front the render. The disclosure label above is burned into every frame the presenter appears in.`
                    : 'Word timings drive the karaoke captions and the SRT exported with the final video.'}
                </p>
              </div>
            </Card>
          </div>
        </div>

        <div className="mt-10 flex items-center justify-between gap-4 flex-wrap">
          <p className="text-sm text-plum-800/60">
            {hasAudio
              ? 'Narration available for the previewed scene.'
              : 'No narration generated yet for the previewed scene.'}
          </p>
          <Button onClick={() => navigate('/admin/approval')} disabled={controlsLocked}>
            Send for officer approval
          </Button>
        </div>
      </div>
    </PageShell>
  )
}
